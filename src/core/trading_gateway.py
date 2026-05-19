"""
Unified Trading Gateway - 统一交易接口层

支持模拟交易（虚拟盘）和实盘交易的统一接口。
通过配置切换不同的交易环境，策略代码无需修改。

V3.1.0: Initial release

Usage:
    >>> from src.core.trading_gateway import TradingGateway, TradingMode
    >>> 
    >>> # 模拟交易
    >>> gateway = TradingGateway(mode=TradingMode.PAPER)
    >>> gateway.connect()
    >>> order_id = gateway.buy("600519.SH", 100, price=1800.0)
    >>> 
    >>> # 实盘交易
    >>> gateway = TradingGateway(
    ...     mode=TradingMode.LIVE,
    ...     broker="eastmoney",
    ...     config={"account": "xxx", "password": "xxx"}
    ... )
"""
from __future__ import annotations

import uuid
import time
import importlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from queue import Queue
from typing import Any, Callable, Dict, List, Optional, Protocol

from src.core.events import EventEngine, Event, EventType
from src.core.interfaces import (
    AccountInfo, OrderInfo, PositionInfo, TradeInfo,
    Side, OrderTypeEnum, OrderStatusEnum
)
from src.core.logger import get_logger
from src.core.audit import AuditLogger, audit_event
from src.core.auth import Authorizer, Permission, ResourceScope, Subject
from src.gateways.base_live_gateway import (
    GatewayConfig as LiveGatewayConfig,
    BaseLiveGateway,
)

logger = get_logger("trading_gateway")

try:
    import easytrader  # type: ignore
except ImportError:
    easytrader = None

try:
    from futu import (  # type: ignore
        OpenSecTradeContext,
        TrdSide,
        OrderType as FutuOrderType,
        RET_OK,
    )
except ImportError:
    OpenSecTradeContext = None
    TrdSide = None
    FutuOrderType = None
    RET_OK = None

try:
    from ib_insync import IB, Stock, MarketOrder, LimitOrder  # type: ignore
except ImportError:
    IB = None
    Stock = None
    MarketOrder = None
    LimitOrder = None


# ---------------------------------------------------------------------------
# Trading Mode & Status
# ---------------------------------------------------------------------------

class TradingMode(str, Enum):
    """Trading mode enumeration."""
    BACKTEST = "backtest"   # 历史回测
    PAPER = "paper"         # 模拟交易（虚拟盘）
    LIVE = "live"           # 实盘交易


class GatewayStatus(str, Enum):
    """Gateway connection status."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATED = "authenticated"
    ERROR = "error"


class BrokerType(str, Enum):
    """Supported broker types."""
    PAPER = "paper"             # 内置模拟撮合
    EASTMONEY = "eastmoney"     # 东方财富
    FUTU = "futu"               # 富途证券
    XUEQIU = "xueqiu"           # 雪球
    IB = "ib"                   # Interactive Brokers
    CTP = "ctp"                 # 中国期货CTP
    QMT = "qmt"                 # QMT alias, defaults to self-built XtQuant adapter
    XTQUANT = "xtquant"         # XtQuant/QMT
    VNPY = "vnpy"               # vn.py routed gateway
    VNPY_QMT = "vnpy_qmt"       # Third-party vn.py QMT gateway
    XTP = "xtp"                 # 中泰证券XTP
    HUNDSUN = "hundsun"         # 恒生UFT


# ---------------------------------------------------------------------------
# Gateway Configuration
# ---------------------------------------------------------------------------

@dataclass
class GatewayConfig:
    """Trading gateway configuration."""
    mode: TradingMode = TradingMode.PAPER
    broker: BrokerType = BrokerType.PAPER
    
    # Connection settings
    host: str = ""
    port: int = 0
    api_key: str = ""
    secret: str = ""
    account: str = ""
    password: str = ""

    # Live gateway specific (XtQuant/XTP/Hundsun)
    terminal_type: str = "QMT"
    terminal_path: str = ""
    trade_server: str = ""
    quote_server: str = ""
    client_id: int = 1
    td_front: str = ""
    md_front: str = ""
    sdk_path: str = ""
    sdk_log_path: str = ""

    # Provider routing. Defaults keep the project-owned implementations active.
    gateway_provider: str = "self"
    qmt_provider: str = "self"
    vnpy_gateway: str = ""
    vnpy_setting: Dict[str, Any] = field(default_factory=dict)
    
    # Trading settings
    initial_cash: float = 1_000_000.0
    commission_rate: float = 0.0003
    slippage: float = 0.0001
    
    # Risk settings
    enable_risk_check: bool = True
    max_position_pct: float = 0.3
    max_order_value: float = 100_000.0
    
    # Misc
    testnet: bool = True  # Use testnet/sandbox by default
    broker_options: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Broker Adapter Protocol
# ---------------------------------------------------------------------------

class BrokerAdapter(Protocol):
    """Protocol for broker-specific adapters."""
    
    def connect(self) -> bool:
        """Connect to broker."""
        ...
    
    def disconnect(self) -> None:
        """Disconnect from broker."""
        ...
    
    def is_connected(self) -> bool:
        """Check connection status."""
        ...
    
    def submit_order(
        self,
        symbol: str,
        side: Side,
        quantity: float,
        price: Optional[float] = None,
        order_type: OrderTypeEnum = OrderTypeEnum.LIMIT
    ) -> str:
        """Submit order and return order ID."""
        ...
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel order."""
        ...
    
    def query_order(self, order_id: str) -> Optional[OrderInfo]:
        """Query order status."""
        ...
    
    def query_account(self) -> AccountInfo:
        """Query account info."""
        ...
    
    def query_positions(self) -> Dict[str, PositionInfo]:
        """Query all positions."""
        ...


class BaseLiveGatewayAdapter:
    """
    Adapter that wraps BaseLiveGateway implementations (XtQuant/XTP/Hundsun).
    """

    def __init__(self, config: GatewayConfig, gateway_cls: type[BaseLiveGateway]):
        self.config = config
        self._event_queue: Queue = Queue()
        self._gateway = gateway_cls(self._build_live_config(), self._event_queue)

    def connect(self) -> bool:
        return self._gateway.connect()

    def disconnect(self) -> None:
        self._gateway.disconnect()

    def is_connected(self) -> bool:
        return bool(self._gateway.is_connected)

    def submit_order(
        self,
        symbol: str,
        side: Side,
        quantity: float,
        price: Optional[float] = None,
        order_type: OrderTypeEnum = OrderTypeEnum.LIMIT,
    ) -> str:
        return self._gateway.send_order(
            symbol=symbol,
            side=side.value,
            quantity=quantity,
            price=price,
            order_type=order_type.value,
        )

    def cancel_order(self, order_id: str) -> bool:
        return self._gateway.cancel_order(order_id)

    def query_order(self, order_id: str) -> Optional[OrderInfo]:
        order = self._gateway.get_order(order_id)
        if not order:
            return None
        return OrderInfo(
            order_id=order.client_order_id,
            symbol=order.symbol,
            side=Side(order.side.value),
            order_type=OrderTypeEnum(order.order_type.value),
            price=order.price,
            quantity=order.quantity,
            filled_quantity=order.filled_quantity,
            avg_fill_price=order.avg_fill_price,
            status=_map_live_order_status(order.status.value),
            create_time=order.create_time,
            update_time=order.update_time,
        )

    def query_account(self) -> AccountInfo:
        update = self._gateway.query_account()
        if not update:
            return AccountInfo(account_id=self._account_id())
        total_value = update.equity or (update.cash + update.unrealized_pnl)
        return AccountInfo(
            account_id=update.account_id,
            cash=update.cash,
            total_value=total_value,
            available=update.available,
            margin=update.margin,
            unrealized_pnl=update.unrealized_pnl,
            realized_pnl=update.realized_pnl,
        )

    def query_positions(self) -> Dict[str, PositionInfo]:
        positions: Dict[str, PositionInfo] = {}
        updates = self._gateway.query_positions()
        for pos in updates:
            positions[pos.symbol] = PositionInfo(
                symbol=pos.symbol,
                size=pos.total_quantity,
                avg_price=pos.avg_price,
                market_value=pos.market_value,
                unrealized_pnl=pos.unrealized_pnl,
                realized_pnl=pos.realized_pnl,
            )
        return positions

    def query_orders(self, symbol: Optional[str] = None) -> List[OrderInfo]:
        orders = []
        for order in self._gateway.get_orders(symbol=symbol):
            orders.append(
                OrderInfo(
                    order_id=order.client_order_id,
                    symbol=order.symbol,
                    side=Side(order.side.value),
                    order_type=OrderTypeEnum(order.order_type.value),
                    price=order.price,
                    quantity=order.quantity,
                    filled_quantity=order.filled_quantity,
                    avg_fill_price=order.avg_fill_price,
                    status=_map_live_order_status(order.status.value),
                    create_time=order.create_time,
                    update_time=order.update_time,
                )
            )
        return orders

    def query_trades(
        self,
        symbol: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[TradeInfo]:
        trades = []
        for trade in self._gateway.get_recent_trades(symbol=symbol, limit=limit):
            trades.append(
                TradeInfo(
                    trade_id=trade.trade_id,
                    order_id=trade.client_order_id,
                    symbol=trade.symbol,
                    side=Side(trade.side.value),
                    price=trade.price,
                    quantity=trade.quantity,
                    commission=trade.commission,
                    timestamp=trade.trade_time,
                )
            )
        return trades

    def _account_id(self) -> str:
        return self.config.account or "default"

    def _build_live_config(self) -> LiveGatewayConfig:
        return LiveGatewayConfig(
            account_id=self._account_id(),
            broker=self.config.broker.value,
            password=self.config.password or None,
            terminal_type=self.config.terminal_type or "QMT",
            terminal_path=self.config.terminal_path or None,
            trade_server=self.config.trade_server or None,
            quote_server=self.config.quote_server or None,
            client_id=self.config.client_id or 1,
            td_front=self.config.td_front or None,
            md_front=self.config.md_front or None,
            sdk_path=self.config.sdk_path or None,
            sdk_log_path=self.config.sdk_log_path or None,
        )


class XtQuantAdapter(BaseLiveGatewayAdapter):
    def __init__(self, config: GatewayConfig):
        from src.gateways.xtquant_gateway import XtQuantGateway
        super().__init__(config, XtQuantGateway)


class XtpAdapter(BaseLiveGatewayAdapter):
    def __init__(self, config: GatewayConfig):
        from src.gateways.xtp_gateway import XtpGateway
        super().__init__(config, XtpGateway)


class HundsunUftAdapter(BaseLiveGatewayAdapter):
    def __init__(self, config: GatewayConfig):
        from src.gateways.hundsun_uft_gateway import HundsunUftGateway
        super().__init__(config, HundsunUftGateway)


class VnpyGatewayAdapter:
    """
    Adapter for vn.py gateways.

    The adapter loads vn.py and the concrete gateway package lazily so normal
    paper/self-built QMT imports do not probe optional third-party SDKs.
    """

    DEFAULT_GATEWAY_CLASSES = {
        "CTP": ("vnpy_ctp", "CtpGateway"),
        "XTP": ("vnpy_xtp", "XtpGateway"),
        "QMT": ("vnpy_qmt", "QmtGateway"),
        "XTQUANT": ("vnpy_qmt", "QmtGateway"),
        "VNPY_QMT": ("vnpy_qmt", "QmtGateway"),
    }

    def __init__(self, config: GatewayConfig):
        self.config = config
        self._connected = False
        self._event_engine = None
        self._main_engine = None
        self._constant_module = None
        self._object_module = None
        self._order_symbols: Dict[str, str] = {}

    def connect(self) -> bool:
        event_engine_cls, main_engine_cls, gateway_cls = self._load_vnpy_components()
        self._event_engine = event_engine_cls()
        self._main_engine = main_engine_cls(self._event_engine)
        self._main_engine.add_gateway(gateway_cls)
        self._main_engine.connect(self._connect_setting(), self._gateway_name())
        self._connected = True
        return True

    def disconnect(self) -> None:
        if self._main_engine is not None:
            close = getattr(self._main_engine, "close", None)
            if callable(close):
                close()
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def submit_order(
        self,
        symbol: str,
        side: Side,
        quantity: float,
        price: Optional[float] = None,
        order_type: OrderTypeEnum = OrderTypeEnum.LIMIT,
    ) -> str:
        main_engine = self._require_main_engine()
        order_request_cls = getattr(self._object_module, "OrderRequest")
        symbol_code, exchange = self._parse_symbol(symbol)
        request = order_request_cls(
            symbol=symbol_code,
            exchange=exchange,
            direction=self._direction(side),
            type=self._order_type(order_type),
            volume=quantity,
            price=0 if price is None else price,
            offset=self._offset(),
        )
        vt_orderid = str(main_engine.send_order(request, self._gateway_name()))
        if vt_orderid:
            self._order_symbols[vt_orderid] = symbol
        return vt_orderid

    def cancel_order(self, order_id: str) -> bool:
        main_engine = self._require_main_engine()
        request = self._cancel_request(main_engine, order_id)
        if request is None:
            return False
        main_engine.cancel_order(request, self._gateway_name())
        return True

    def query_order(self, order_id: str) -> Optional[OrderInfo]:
        main_engine = self._require_main_engine()
        getter = getattr(main_engine, "get_order", None)
        if callable(getter):
            order = getter(order_id)
            if order is not None:
                return self._map_order(order)
        for order in self._all_orders():
            if getattr(order, "vt_orderid", None) == order_id or getattr(order, "orderid", None) == order_id:
                return self._map_order(order)
        return None

    def query_account(self) -> AccountInfo:
        main_engine = self._require_main_engine()
        getter = getattr(main_engine, "get_all_accounts", None)
        accounts = getter() if callable(getter) else []
        if not accounts:
            return AccountInfo(account_id=self.config.account or "vnpy")
        account = accounts[0]
        account_id = str(
            getattr(account, "accountid", "")
            or getattr(account, "account_id", "")
            or getattr(account, "vt_accountid", "")
            or self.config.account
            or "vnpy"
        )
        cash = _float_attr(account, "cash", "available", "available_cash")
        available = _float_attr(account, "available", "available_cash", "cash")
        total_value = _float_attr(account, "balance", "equity", "total_value")
        if total_value == 0:
            total_value = cash + _float_attr(account, "frozen")
        return AccountInfo(
            account_id=account_id,
            cash=cash,
            total_value=total_value,
            available=available,
            margin=_float_attr(account, "margin"),
        )

    def query_positions(self) -> Dict[str, PositionInfo]:
        main_engine = self._require_main_engine()
        getter = getattr(main_engine, "get_all_positions", None)
        raw_positions = getter() if callable(getter) else []
        positions: Dict[str, PositionInfo] = {}
        for pos in raw_positions:
            symbol = str(getattr(pos, "vt_symbol", "") or getattr(pos, "symbol", ""))
            size = _float_attr(pos, "volume", "total_quantity")
            avg_price = _float_attr(pos, "price", "avg_price")
            positions[symbol] = PositionInfo(
                symbol=symbol,
                size=size,
                avg_price=avg_price,
                market_value=_float_attr(pos, "market_value") or size * avg_price,
                unrealized_pnl=_float_attr(pos, "pnl", "unrealized_pnl"),
                realized_pnl=_float_attr(pos, "realized_pnl"),
            )
        return positions

    def query_orders(self, symbol: Optional[str] = None) -> List[OrderInfo]:
        orders = [self._map_order(order) for order in self._all_orders()]
        if symbol:
            orders = [order for order in orders if order.symbol == symbol]
        return orders

    def query_trades(
        self,
        symbol: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[TradeInfo]:
        main_engine = self._require_main_engine()
        getter = getattr(main_engine, "get_all_trades", None)
        trades = [self._map_trade(trade) for trade in (getter() if callable(getter) else [])]
        if symbol:
            trades = [trade for trade in trades if trade.symbol == symbol]
        if limit is not None and limit >= 0:
            trades = trades[:limit]
        return trades

    def _all_orders(self) -> List[Any]:
        main_engine = self._require_main_engine()
        getter = getattr(main_engine, "get_all_active_orders", None)
        if callable(getter):
            return list(getter())
        return []

    def _load_vnpy_components(self):
        try:
            event_module = importlib.import_module("vnpy.event")
            engine_module = importlib.import_module("vnpy.trader.engine")
            self._constant_module = importlib.import_module("vnpy.trader.constant")
            self._object_module = importlib.import_module("vnpy.trader.object")
        except ImportError as exc:
            raise RuntimeError("vn.py is not installed. Install vnpy and the required gateway package first.") from exc

        return (
            getattr(event_module, "EventEngine"),
            getattr(engine_module, "MainEngine"),
            self._load_gateway_class(),
        )

    def _load_gateway_class(self):
        class_path = str(self.config.broker_options.get("vnpy_gateway_class", "")).strip()
        if class_path:
            module_name, _, class_name = class_path.rpartition(".")
            if not module_name or not class_name:
                raise ValueError("broker_options.vnpy_gateway_class must be a full import path.")
        else:
            module_name, class_name = self.DEFAULT_GATEWAY_CLASSES.get(
                self._gateway_name().upper(),
                (f"vnpy_{self._gateway_name().lower()}", f"{self._gateway_name().title()}Gateway"),
            )
        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:
            raise RuntimeError(
                f"vn.py gateway package '{module_name}' is not installed. "
                "Install it or set broker_options.vnpy_gateway_class to a custom gateway class."
            ) from exc
        return getattr(module, class_name)

    def _connect_setting(self) -> Dict[str, Any]:
        if self.config.vnpy_setting:
            return dict(self.config.vnpy_setting)
        setting = self.config.broker_options.get("vnpy_setting")
        if isinstance(setting, dict):
            return dict(setting)
        return {
            key: value
            for key, value in self.config.broker_options.items()
            if key not in {"vnpy_gateway_class", "vnpy_gateway", "vnpy_setting"}
        }

    def _gateway_name(self) -> str:
        configured = self.config.vnpy_gateway or str(self.config.broker_options.get("vnpy_gateway", "")).strip()
        if configured:
            return configured
        if self.config.broker == BrokerType.VNPY_QMT:
            return "QMT"
        if self.config.broker == BrokerType.VNPY:
            raise ValueError("vnpy_gateway is required when broker is 'vnpy'.")
        return self.config.broker.value.upper()

    def _parse_symbol(self, symbol: str):
        if "." in symbol:
            symbol_code, exchange_code = symbol.rsplit(".", 1)
        else:
            symbol_code = symbol
            exchange_code = str(self.config.broker_options.get("exchange", "SSE"))
        exchange_aliases = {"SH": "SSE", "SHSE": "SSE", "SZ": "SZSE", "SZE": "SZSE"}
        member = exchange_aliases.get(exchange_code.upper(), exchange_code.upper())
        return symbol_code, self._constant("Exchange", member)

    def _direction(self, side: Side):
        return self._constant("Direction", "LONG" if side == Side.BUY else "SHORT")

    def _order_type(self, order_type: OrderTypeEnum):
        member = "MARKET" if order_type == OrderTypeEnum.MARKET else "LIMIT"
        return self._constant("OrderType", member)

    def _offset(self):
        member = str(self.config.broker_options.get("vnpy_offset", "OPEN")).upper()
        return self._constant("Offset", member)

    def _constant(self, enum_name: str, member: str):
        enum_cls = getattr(self._constant_module, enum_name)
        return getattr(enum_cls, member)

    def _cancel_request(self, main_engine, order_id: str):
        getter = getattr(main_engine, "get_order", None)
        order = getter(order_id) if callable(getter) else None
        if order is not None and hasattr(order, "create_cancel_request"):
            return order.create_cancel_request()
        symbol = self._order_symbols.get(order_id) or str(self.config.broker_options.get("cancel_symbol", ""))
        if not symbol:
            return None
        cancel_request_cls = getattr(self._object_module, "CancelRequest")
        symbol_code, exchange = self._parse_symbol(symbol)
        return cancel_request_cls(orderid=order_id.split(".")[-1], symbol=symbol_code, exchange=exchange)

    def _map_order(self, order: Any) -> OrderInfo:
        symbol = str(getattr(order, "vt_symbol", "") or getattr(order, "symbol", ""))
        direction = _enum_token(getattr(order, "direction", ""))
        order_type = _enum_token(getattr(order, "type", ""))
        return OrderInfo(
            order_id=str(getattr(order, "vt_orderid", "") or getattr(order, "orderid", "")),
            symbol=symbol,
            side=Side.SELL if direction in {"SHORT", "SELL"} else Side.BUY,
            order_type=OrderTypeEnum.MARKET if order_type == "MARKET" else OrderTypeEnum.LIMIT,
            price=_optional_float(getattr(order, "price", None)),
            quantity=_float_attr(order, "volume", "quantity"),
            filled_quantity=_float_attr(order, "traded", "filled_quantity"),
            avg_fill_price=_float_attr(order, "avg_price", "avg_fill_price"),
            status=_map_vnpy_order_status(getattr(order, "status", "")),
            create_time=_normalize_datetime(getattr(order, "datetime", None)),
            update_time=_normalize_datetime(getattr(order, "datetime", None)),
        )

    def _map_trade(self, trade: Any) -> TradeInfo:
        direction = _enum_token(getattr(trade, "direction", ""))
        return TradeInfo(
            trade_id=str(getattr(trade, "vt_tradeid", "") or getattr(trade, "tradeid", "")),
            order_id=str(getattr(trade, "vt_orderid", "") or getattr(trade, "orderid", "")),
            symbol=str(getattr(trade, "vt_symbol", "") or getattr(trade, "symbol", "")),
            side=Side.SELL if direction in {"SHORT", "SELL"} else Side.BUY,
            price=_float_attr(trade, "price"),
            quantity=_float_attr(trade, "volume", "quantity"),
            commission=_float_attr(trade, "commission"),
            timestamp=_normalize_datetime(getattr(trade, "datetime", None)),
        )

    def _require_main_engine(self):
        if self._main_engine is None:
            raise RuntimeError("vn.py gateway is not connected")
        return self._main_engine


def register_qmt_provider(name: str, factory: Callable[[GatewayConfig], BrokerAdapter]) -> None:
    """Register a QMT provider factory for runtime/provider-specific extensions."""
    QMT_PROVIDER_REGISTRY[_normalize_provider(name)] = factory


def available_qmt_providers() -> List[str]:
    """Return available QMT provider names."""
    return sorted(QMT_PROVIDER_REGISTRY.keys())


def _normalize_provider(value: str) -> str:
    return (value or "self").strip().lower().replace("-", "_")


def _self_qmt_adapter(config: GatewayConfig) -> BrokerAdapter:
    return XtQuantAdapter(config)


def _vnpy_qmt_adapter(config: GatewayConfig) -> BrokerAdapter:
    if not config.vnpy_gateway:
        config.vnpy_gateway = "QMT"
    return VnpyGatewayAdapter(config)


QMT_PROVIDER_REGISTRY: Dict[str, Callable[[GatewayConfig], BrokerAdapter]] = {
    "self": _self_qmt_adapter,
    "xtquant": _self_qmt_adapter,
    "vnpy": _vnpy_qmt_adapter,
    "vnpy_qmt": _vnpy_qmt_adapter,
    "third_party": _vnpy_qmt_adapter,
}


# ---------------------------------------------------------------------------
# Paper Trading Adapter (内置模拟撮合)
# ---------------------------------------------------------------------------

class PaperTradingAdapter:
    """
    Paper trading adapter with simulated order matching.
    
    支持:
    - 市价单、限价单、止损单
    - 模拟成交（下一Bar开盘价）
    - 手续费和滑点计算
    - 实时持仓和资金更新
    """
    
    def __init__(self, config: GatewayConfig):
        self.config = config
        self._connected = False
        
        # Account state
        self._cash = config.initial_cash
        self._positions: Dict[str, PositionInfo] = {}
        self._orders: Dict[str, OrderInfo] = {}
        self._trades: List[TradeInfo] = []
        
        # Order management
        self._order_seq = 0
        self._pending_orders: Dict[str, OrderInfo] = {}
        
        # Market data (for order matching)
        self._last_prices: Dict[str, float] = {}
    
    def connect(self) -> bool:
        """Simulate connection."""
        logger.info("Paper trading connected", initial_cash=self._cash)
        self._connected = True
        return True
    
    def disconnect(self) -> None:
        """Simulate disconnection."""
        logger.info("Paper trading disconnected")
        self._connected = False
    
    def is_connected(self) -> bool:
        return self._connected
    
    def submit_order(
        self,
        symbol: str,
        side: Side,
        quantity: float,
        price: Optional[float] = None,
        order_type: OrderTypeEnum = OrderTypeEnum.LIMIT
    ) -> str:
        """Submit order to paper trading system."""
        self._order_seq += 1
        order_id = f"PAPER-{self._order_seq:08d}"
        
        order = OrderInfo(
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            price=price,
            quantity=quantity,
            status=OrderStatusEnum.SUBMITTED,
            create_time=datetime.now()
        )
        
        self._orders[order_id] = order
        self._pending_orders[order_id] = order
        
        logger.info(
            "Order submitted",
            order_id=order_id,
            symbol=symbol,
            side=side.value,
            quantity=quantity,
            price=price
        )
        
        # For market orders, execute immediately at last price
        if order_type == OrderTypeEnum.MARKET:
            fill_price = self._last_prices.get(symbol, price or 0)
            if fill_price > 0:
                self._execute_order(order_id, fill_price)
        
        return order_id
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel pending order."""
        if order_id not in self._pending_orders:
            logger.warning("Order not found or already filled", order_id=order_id)
            return False
        
        order = self._orders[order_id]
        order.status = OrderStatusEnum.CANCELLED
        order.update_time = datetime.now()
        del self._pending_orders[order_id]
        
        logger.info("Order cancelled", order_id=order_id)
        return True
    
    def query_order(self, order_id: str) -> Optional[OrderInfo]:
        return self._orders.get(order_id)
    
    def query_account(self) -> AccountInfo:
        total_value = self._cash
        unrealized_pnl = 0.0
        
        for pos in self._positions.values():
            last_price = self._last_prices.get(pos.symbol, pos.avg_price)
            market_value = pos.size * last_price
            total_value += market_value
            unrealized_pnl += pos.size * (last_price - pos.avg_price)
        
        return AccountInfo(
            account_id="PAPER",
            cash=self._cash,
            total_value=total_value,
            available=self._cash,
            unrealized_pnl=unrealized_pnl
        )
    
    def query_positions(self) -> Dict[str, PositionInfo]:
        return self._positions.copy()

    def query_orders(self, symbol: Optional[str] = None) -> List[OrderInfo]:
        orders = list(self._orders.values())
        if symbol is not None:
            orders = [order for order in orders if order.symbol == symbol]
        orders.sort(key=lambda order: order.update_time or order.create_time or datetime.min, reverse=True)
        return orders

    def query_trades(
        self,
        symbol: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[TradeInfo]:
        trades = self._trades
        if symbol is not None:
            trades = [trade for trade in trades if trade.symbol == symbol]
        trades = sorted(trades, key=lambda trade: trade.timestamp or datetime.min, reverse=True)
        if limit is not None and limit >= 0:
            return trades[:limit]
        return trades
    
    def update_price(self, symbol: str, price: float) -> None:
        """Update market price and check pending orders."""
        self._last_prices[symbol] = price
        
        # Check pending limit orders
        for order_id in list(self._pending_orders.keys()):
            order = self._pending_orders[order_id]
            if order.symbol != symbol:
                continue
            
            if order.order_type == OrderTypeEnum.LIMIT:
                # Buy limit: fill if price <= limit
                # Sell limit: fill if price >= limit
                if order.side == Side.BUY and price <= order.price:
                    self._execute_order(order_id, price)
                elif order.side == Side.SELL and price >= order.price:
                    self._execute_order(order_id, price)
            
            elif order.order_type == OrderTypeEnum.STOP:
                # Buy stop: fill if price >= stop
                # Sell stop: fill if price <= stop
                if order.side == Side.BUY and price >= order.price:
                    self._execute_order(order_id, price)
                elif order.side == Side.SELL and price <= order.price:
                    self._execute_order(order_id, price)
    
    def _execute_order(self, order_id: str, fill_price: float) -> None:
        """Execute order at given price."""
        order = self._orders.get(order_id)
        if not order or order.status not in (OrderStatusEnum.SUBMITTED, OrderStatusEnum.PENDING):
            return
        
        # Apply slippage
        slippage = fill_price * self.config.slippage
        if order.side == Side.BUY:
            fill_price += slippage
        else:
            fill_price -= slippage
        
        # Calculate commission
        commission = fill_price * order.quantity * self.config.commission_rate
        
        # Update position
        pos = self._positions.get(order.symbol, PositionInfo(symbol=order.symbol))
        
        if order.side == Side.BUY:
            # Buy: increase position
            total_cost = pos.size * pos.avg_price + order.quantity * fill_price
            pos.size += order.quantity
            pos.avg_price = total_cost / pos.size if pos.size > 0 else 0
            self._cash -= order.quantity * fill_price + commission
        else:
            # Sell: decrease position
            if pos.size >= order.quantity:
                realized_pnl = order.quantity * (fill_price - pos.avg_price)
                pos.realized_pnl += realized_pnl
                pos.size -= order.quantity
                self._cash += order.quantity * fill_price - commission
        
        self._positions[order.symbol] = pos
        
        # Update order
        order.filled_quantity = order.quantity
        order.avg_fill_price = fill_price
        order.status = OrderStatusEnum.FILLED
        order.update_time = datetime.now()
        
        # Remove from pending
        if order_id in self._pending_orders:
            del self._pending_orders[order_id]
        
        # Record trade
        trade = TradeInfo(
            trade_id=f"TRADE-{len(self._trades)+1:08d}",
            order_id=order_id,
            symbol=order.symbol,
            side=order.side,
            price=fill_price,
            quantity=order.quantity,
            commission=commission,
            timestamp=datetime.now()
        )
        self._trades.append(trade)
        
        logger.info(
            "Order filled",
            order_id=order_id,
            symbol=order.symbol,
            side=order.side.value,
            price=fill_price,
            quantity=order.quantity,
            commission=commission
        )

    # ---------------------------------------------------------------------------
    # Snapshot / Restore
    # ---------------------------------------------------------------------------

    def snapshot_state(self) -> Dict[str, Any]:
        return {
            "cash": self._cash,
            "positions": [self._serialize_position(p) for p in self._positions.values()],
            "orders": [self._serialize_order(o) for o in self._orders.values()],
            "trades": [self._serialize_trade(t) for t in self._trades],
            "last_prices": dict(self._last_prices),
        }

    def restore_state(self, payload: Dict[str, Any]) -> None:
        self._cash = float(payload.get("cash", self._cash))
        self._positions = {p.symbol: p for p in (self._deserialize_position(d) for d in payload.get("positions", []))}
        self._orders = {o.order_id: o for o in (self._deserialize_order(d) for d in payload.get("orders", []))}
        self._pending_orders = {
            oid: o for oid, o in self._orders.items()
            if o.status in (OrderStatusEnum.SUBMITTED, OrderStatusEnum.PENDING)
        }
        self._trades = [self._deserialize_trade(d) for d in payload.get("trades", [])]
        self._last_prices = dict(payload.get("last_prices", {}))

    @staticmethod
    def _serialize_position(pos: PositionInfo) -> Dict[str, Any]:
        return {
            "symbol": pos.symbol,
            "size": pos.size,
            "avg_price": pos.avg_price,
            "market_value": pos.market_value,
            "unrealized_pnl": pos.unrealized_pnl,
            "realized_pnl": pos.realized_pnl,
        }

    @staticmethod
    def _deserialize_position(data: Dict[str, Any]) -> PositionInfo:
        return PositionInfo(
            symbol=data["symbol"],
            size=float(data.get("size", 0.0)),
            avg_price=float(data.get("avg_price", 0.0)),
            market_value=float(data.get("market_value", 0.0)),
            unrealized_pnl=float(data.get("unrealized_pnl", 0.0)),
            realized_pnl=float(data.get("realized_pnl", 0.0)),
        )

    @staticmethod
    def _serialize_order(order: OrderInfo) -> Dict[str, Any]:
        return {
            "order_id": order.order_id,
            "symbol": order.symbol,
            "side": order.side.value,
            "order_type": order.order_type.value,
            "price": order.price,
            "quantity": order.quantity,
            "filled_quantity": order.filled_quantity,
            "avg_fill_price": order.avg_fill_price,
            "status": order.status.value,
            "create_time": order.create_time.isoformat() if order.create_time else None,
            "update_time": order.update_time.isoformat() if order.update_time else None,
        }

    @staticmethod
    def _deserialize_order(data: Dict[str, Any]) -> OrderInfo:
        return OrderInfo(
            order_id=data["order_id"],
            symbol=data["symbol"],
            side=Side(data["side"]),
            order_type=OrderTypeEnum(data["order_type"]),
            price=data.get("price"),
            quantity=float(data.get("quantity", 0.0)),
            filled_quantity=float(data.get("filled_quantity", 0.0)),
            avg_fill_price=float(data.get("avg_fill_price", 0.0)),
            status=OrderStatusEnum(data.get("status", OrderStatusEnum.PENDING.value)),
            create_time=_parse_dt(data.get("create_time")),
            update_time=_parse_dt(data.get("update_time")),
        )

    @staticmethod
    def _serialize_trade(trade: TradeInfo) -> Dict[str, Any]:
        return {
            "trade_id": trade.trade_id,
            "order_id": trade.order_id,
            "symbol": trade.symbol,
            "side": trade.side.value,
            "price": trade.price,
            "quantity": trade.quantity,
            "commission": trade.commission,
            "timestamp": trade.timestamp.isoformat() if trade.timestamp else None,
        }

    @staticmethod
    def _deserialize_trade(data: Dict[str, Any]) -> TradeInfo:
        return TradeInfo(
            trade_id=data["trade_id"],
            order_id=data["order_id"],
            symbol=data["symbol"],
            side=Side(data["side"]),
            price=float(data.get("price", 0.0)),
            quantity=float(data.get("quantity", 0.0)),
            commission=float(data.get("commission", 0.0)),
            timestamp=_parse_dt(data.get("timestamp")),
        )


# ---------------------------------------------------------------------------
# Broker Adapters (Stubs for real broker integration)
# ---------------------------------------------------------------------------

class EastMoneyAdapter:
    """
    东方财富 API 适配器 (Stub)
    
    实际实现需要:
    - easytrader 库
    - 客户端 (同花顺/通达信)
    
    Reference:
    - https://github.com/shidenggui/easytrader
    """
    
    def __init__(self, config: GatewayConfig):
        self.config = config
        self._connected = False
        self._client = None
    
    def connect(self) -> bool:
        logger.info("Connecting to EastMoney...")
        if easytrader is None:
            raise NotImplementedError("easytrader not installed. Install easytrader first.")

        client_type = self.config.broker_options.get("client_type", "universal_client")
        self._client = easytrader.use(client_type)

        exe_path = self.config.broker_options.get("exe_path") or self.config.host or ""
        kwargs = dict(self.config.broker_options.get("connect_kwargs", {}))
        if hasattr(self._client, "connect"):
            if exe_path:
                kwargs.setdefault("exe_path", exe_path)
            self._client.connect(**kwargs)
        elif hasattr(self._client, "prepare"):
            if exe_path:
                self._client.prepare(exe_path, **kwargs)
        self._connected = True
        return True
    
    def disconnect(self) -> None:
        self._connected = False
    
    def is_connected(self) -> bool:
        return self._connected
    
    def submit_order(self, symbol: str, side: Side, quantity: float, 
                     price: Optional[float] = None, order_type: OrderTypeEnum = OrderTypeEnum.LIMIT) -> str:
        if not self._client:
            raise RuntimeError("EastMoney client not connected")
        if side == Side.BUY:
            result = self._client.buy(code=symbol, price=price or 0.0, amount=quantity)
        else:
            result = self._client.sell(code=symbol, price=price or 0.0, amount=quantity)
        if isinstance(result, dict):
            return str(result.get("order_id") or result.get("entrust_no") or result.get("id") or "")
        return str(result)
    
    def cancel_order(self, order_id: str) -> bool:
        if not self._client:
            raise RuntimeError("EastMoney client not connected")
        if hasattr(self._client, "cancel_entrust"):
            result = self._client.cancel_entrust(order_id)
            return bool(result)
        if hasattr(self._client, "cancel_order"):
            result = self._client.cancel_order(order_id)
            return bool(result)
        raise NotImplementedError("cancel_order not supported by easytrader client")
    
    def query_order(self, order_id: str) -> Optional[OrderInfo]:
        if not self._client:
            return None
        if hasattr(self._client, "get_order"):
            data = self._client.get_order(order_id)
            if isinstance(data, dict):
                return OrderInfo(
                    order_id=str(order_id),
                    symbol=str(data.get("symbol", "")),
                    side=Side(data.get("side", "buy")),
                    order_type=OrderTypeEnum.LIMIT,
                    price=float(data.get("price", 0.0)),
                    quantity=float(data.get("quantity", 0.0)),
                )
        return None
    
    def query_account(self) -> AccountInfo:
        if not self._client:
            raise RuntimeError("EastMoney client not connected")
        balance = getattr(self._client, "balance", None)
        data = balance() if callable(balance) else balance or {}
        cash = float(data.get("cash_balance", data.get("cash", 0.0))) if isinstance(data, dict) else 0.0
        total = float(data.get("asset_balance", data.get("total_asset", cash))) if isinstance(data, dict) else cash
        available = float(data.get("available", cash)) if isinstance(data, dict) else cash
        return AccountInfo(
            account_id=self.config.account or "eastmoney",
            cash=cash,
            total_value=total,
            available=available,
        )
    
    def query_positions(self) -> Dict[str, PositionInfo]:
        if not self._client:
            raise RuntimeError("EastMoney client not connected")
        positions = getattr(self._client, "position", None)
        data = positions() if callable(positions) else positions or []
        results: Dict[str, PositionInfo] = {}
        if isinstance(data, list):
            for row in data:
                symbol = str(row.get("symbol") or row.get("证券代码") or row.get("code") or "")
                size = float(row.get("volume") or row.get("可用余额") or row.get("amount") or 0.0)
                avg_price = float(row.get("avg_price") or row.get("成本价") or 0.0)
                market_value = float(row.get("market_value") or row.get("市值") or 0.0)
                unrealized = float(row.get("unrealized_pnl") or row.get("浮动盈亏") or 0.0)
                results[symbol] = PositionInfo(
                    symbol=symbol,
                    size=size,
                    avg_price=avg_price,
                    market_value=market_value,
                    unrealized_pnl=unrealized,
                )
        return results


class FutuAdapter:
    """
    富途 API 适配器 (Stub)
    
    实际实现需要:
    - futu-api 库
    - FutuOpenD 客户端
    
    Reference:
    - https://openapi.futunn.com/futu-api-doc/
    """
    
    def __init__(self, config: GatewayConfig):
        self.config = config
        self._connected = False
    
    def connect(self) -> bool:
        logger.info("Connecting to Futu OpenD...")
        if OpenSecTradeContext is None:
            raise NotImplementedError("futu-api not installed. Install futu-api first.")
        host = self.config.host or "127.0.0.1"
        port = self.config.port or 11111
        self._ctx = OpenSecTradeContext(host=host, port=port)
        if self.config.password:
            ret, _ = self._ctx.unlock_trade(self.config.password)
            if RET_OK is not None and ret != RET_OK:
                raise RuntimeError("Futu unlock_trade failed")
        self._connected = True
        return True
    
    def disconnect(self) -> None:
        self._connected = False
    
    def is_connected(self) -> bool:
        return self._connected
    
    def submit_order(self, symbol: str, side: Side, quantity: float,
                     price: Optional[float] = None, order_type: OrderTypeEnum = OrderTypeEnum.LIMIT) -> str:
        if not self._ctx:
            raise RuntimeError("Futu context not connected")
        if TrdSide is None or FutuOrderType is None:
            raise RuntimeError("Futu API not available")
        futu_side = TrdSide.BUY if side == Side.BUY else TrdSide.SELL
        if order_type == OrderTypeEnum.MARKET:
            futu_type = FutuOrderType.MARKET
        else:
            futu_type = FutuOrderType.NORMAL
        ret, data = self._ctx.place_order(
            price=price or 0.0,
            qty=quantity,
            code=symbol,
            trd_side=futu_side,
            order_type=futu_type,
        )
        if RET_OK is not None and ret != RET_OK:
            raise RuntimeError(f"Futu place_order failed: {data}")
        order_id = ""
        if hasattr(data, "order_id"):
            order_id = str(data.order_id)
        elif isinstance(data, dict):
            order_id = str(data.get("order_id") or "")
        return order_id
    
    def cancel_order(self, order_id: str) -> bool:
        if not self._ctx:
            raise RuntimeError("Futu context not connected")
        if hasattr(self._ctx, "modify_order"):
            ret, _ = self._ctx.modify_order(order_id=order_id, modify_order_op=0)
        else:
            ret, _ = self._ctx.cancel_order(order_id=order_id)
        if RET_OK is not None and ret != RET_OK:
            return False
        return True
    
    def query_order(self, order_id: str) -> Optional[OrderInfo]:
        if not self._ctx:
            return None
        if hasattr(self._ctx, "order_list_query"):
            ret, data = self._ctx.order_list_query(order_id=order_id)
            if RET_OK is not None and ret != RET_OK:
                return None
            if isinstance(data, dict):
                symbol = str(data.get("code", ""))
                side = Side.BUY if data.get("trd_side") == 0 else Side.SELL
                return OrderInfo(
                    order_id=str(order_id),
                    symbol=symbol,
                    side=side,
                    order_type=OrderTypeEnum.LIMIT,
                    price=float(data.get("price", 0.0)),
                    quantity=float(data.get("qty", 0.0)),
                    status=OrderStatusEnum.SUBMITTED,
                )
        return None
    
    def query_account(self) -> AccountInfo:
        if not self._ctx:
            raise RuntimeError("Futu context not connected")
        if hasattr(self._ctx, "accinfo_query"):
            ret, data = self._ctx.accinfo_query()
            if RET_OK is not None and ret != RET_OK:
                raise RuntimeError("Futu accinfo_query failed")
            if isinstance(data, dict):
                cash = float(data.get("cash", 0.0))
                total = float(data.get("total_assets", cash))
                available = float(data.get("avl_withdrawal_cash", cash))
                return AccountInfo(account_id=self.config.account or "futu", cash=cash, total_value=total, available=available)
        return AccountInfo(account_id=self.config.account or "futu")
    
    def query_positions(self) -> Dict[str, PositionInfo]:
        if not self._ctx:
            raise RuntimeError("Futu context not connected")
        if hasattr(self._ctx, "position_list_query"):
            ret, data = self._ctx.position_list_query()
            if RET_OK is not None and ret != RET_OK:
                raise RuntimeError("Futu position_list_query failed")
            results: Dict[str, PositionInfo] = {}
            if isinstance(data, list):
                for row in data:
                    symbol = str(row.get("code", ""))
                    qty = float(row.get("qty", 0.0))
                    avg_price = float(row.get("cost_price", 0.0))
                    market_value = float(row.get("market_val", 0.0))
                    pnl = float(row.get("pl_val", 0.0))
                    results[symbol] = PositionInfo(
                        symbol=symbol,
                        size=qty,
                        avg_price=avg_price,
                        market_value=market_value,
                        unrealized_pnl=pnl,
                    )
            return results
        return {}


class XueqiuAdapter:
    """
    雪球 API 适配器 (Stub)
    
    实际实现需要:
    - xueqiu 非官方 API
    - Cookie 登录认证
    
    Warning: 雪球无官方交易API，仅供模拟盘使用
    """
    
    def __init__(self, config: GatewayConfig):
        self.config = config
        self._connected = False
    
    def connect(self) -> bool:
        logger.info("Connecting to Xueqiu...")
        if easytrader is None:
            raise NotImplementedError("easytrader not installed. Install easytrader first.")
        client_type = self.config.broker_options.get("client_type", "xq")
        self._client = easytrader.use(client_type)
        cookie = self.config.broker_options.get("cookie")
        if hasattr(self._client, "prepare") and cookie:
            self._client.prepare(cookie=cookie)
        self._connected = True
        return True
    
    def disconnect(self) -> None:
        self._connected = False
    
    def is_connected(self) -> bool:
        return self._connected
    
    def submit_order(self, symbol: str, side: Side, quantity: float,
                     price: Optional[float] = None, order_type: OrderTypeEnum = OrderTypeEnum.LIMIT) -> str:
        if not self._client:
            raise RuntimeError("Xueqiu client not connected")
        if side == Side.BUY:
            result = self._client.buy(code=symbol, price=price or 0.0, amount=quantity)
        else:
            result = self._client.sell(code=symbol, price=price or 0.0, amount=quantity)
        if isinstance(result, dict):
            return str(result.get("order_id") or result.get("id") or "")
        return str(result)
    
    def cancel_order(self, order_id: str) -> bool:
        if not self._client:
            raise RuntimeError("Xueqiu client not connected")
        if hasattr(self._client, "cancel_order"):
            result = self._client.cancel_order(order_id)
            return bool(result)
        if hasattr(self._client, "cancel_entrust"):
            result = self._client.cancel_entrust(order_id)
            return bool(result)
        raise NotImplementedError("cancel_order not supported by Xueqiu client")
    
    def query_order(self, order_id: str) -> Optional[OrderInfo]:
        if not self._client or not hasattr(self._client, "get_order"):
            return None
        data = self._client.get_order(order_id)
        if isinstance(data, dict):
            side = data.get("side", "buy")
            return OrderInfo(
                order_id=str(order_id),
                symbol=str(data.get("symbol", "")),
                side=Side(side),
                order_type=OrderTypeEnum.LIMIT,
                price=float(data.get("price", 0.0)),
                quantity=float(data.get("quantity", 0.0)),
            )
        return None
    
    def query_account(self) -> AccountInfo:
        if not self._client:
            raise RuntimeError("Xueqiu client not connected")
        balance = getattr(self._client, "balance", None)
        data = balance() if callable(balance) else balance or {}
        cash = float(data.get("cash", 0.0)) if isinstance(data, dict) else 0.0
        total = float(data.get("total_asset", cash)) if isinstance(data, dict) else cash
        available = float(data.get("available", cash)) if isinstance(data, dict) else cash
        return AccountInfo(
            account_id=self.config.account or "xueqiu",
            cash=cash,
            total_value=total,
            available=available,
        )
    
    def query_positions(self) -> Dict[str, PositionInfo]:
        if not self._client:
            raise RuntimeError("Xueqiu client not connected")
        positions = getattr(self._client, "position", None)
        data = positions() if callable(positions) else positions or []
        results: Dict[str, PositionInfo] = {}
        if isinstance(data, list):
            for row in data:
                symbol = str(row.get("symbol") or row.get("code") or "")
                size = float(row.get("amount") or row.get("volume") or 0.0)
                avg_price = float(row.get("avg_price") or row.get("cost_price") or 0.0)
                market_value = float(row.get("market_value") or row.get("market_val") or 0.0)
                unrealized = float(row.get("unrealized_pnl") or row.get("profit") or 0.0)
                results[symbol] = PositionInfo(
                    symbol=symbol,
                    size=size,
                    avg_price=avg_price,
                    market_value=market_value,
                    unrealized_pnl=unrealized,
                )
        return results


class IBAdapter:
    """
    Interactive Brokers API 适配器 (Stub)
    
    实际实现需要:
    - ib_insync 库
    - TWS/IB Gateway
    
    Reference:
    - https://ib-insync.readthedocs.io/
    """
    
    def __init__(self, config: GatewayConfig):
        self.config = config
        self._connected = False
        self._client = None
        self._ctx = None
        self._ib = None
        self._orders: Dict[str, Any] = {}
    
    def connect(self) -> bool:
        logger.info("Connecting to Interactive Brokers...")
        if IB is None:
            raise NotImplementedError("ib_insync not installed. Install ib_insync first.")
        host = self.config.host or "127.0.0.1"
        port = self.config.port or 7497
        client_id = self.config.client_id or 1
        self._ib = IB()
        self._ib.connect(host, port, clientId=client_id)
        self._connected = True
        return True
    
    def disconnect(self) -> None:
        if self._ib:
            try:
                self._ib.disconnect()
            except Exception:
                pass
        self._connected = False
    
    def is_connected(self) -> bool:
        return self._connected
    
    def submit_order(self, symbol: str, side: Side, quantity: float,
                     price: Optional[float] = None, order_type: OrderTypeEnum = OrderTypeEnum.LIMIT) -> str:
        if not self._ib:
            raise RuntimeError("IB client not connected")
        if Stock is None or MarketOrder is None or LimitOrder is None:
            raise RuntimeError("ib_insync not available")
        exchange = self.config.broker_options.get("exchange", "SMART")
        currency = self.config.broker_options.get("currency", "USD")
        primary_exchange = self.config.broker_options.get("primary_exchange", "")
        sym = symbol.split(".")[0]
        contract = Stock(sym, exchange, currency)
        if primary_exchange:
            contract.primaryExchange = primary_exchange
        if order_type == OrderTypeEnum.MARKET:
            order = MarketOrder("BUY" if side == Side.BUY else "SELL", quantity)
        else:
            order = LimitOrder("BUY" if side == Side.BUY else "SELL", quantity, price or 0.0)
        trade = self._ib.placeOrder(contract, order)
        order_id = str(trade.order.orderId)
        self._orders[order_id] = trade
        return order_id
    
    def cancel_order(self, order_id: str) -> bool:
        if not self._ib:
            raise RuntimeError("IB client not connected")
        trade = self._orders.get(order_id)
        if not trade:
            return False
        self._ib.cancelOrder(trade.order)
        return True
    
    def query_order(self, order_id: str) -> Optional[OrderInfo]:
        trade = self._orders.get(order_id)
        if not trade:
            return None
        side = Side.BUY if trade.order.action.upper() == "BUY" else Side.SELL
        order_type = OrderTypeEnum.MARKET if trade.order.orderType.upper() == "MKT" else OrderTypeEnum.LIMIT
        return OrderInfo(
            order_id=order_id,
            symbol=str(trade.contract.symbol),
            side=side,
            order_type=order_type,
            price=getattr(trade.order, "lmtPrice", None),
            quantity=float(trade.order.totalQuantity),
            status=OrderStatusEnum.SUBMITTED,
        )
    
    def query_account(self) -> AccountInfo:
        if not self._ib:
            raise RuntimeError("IB client not connected")
        summary = self._ib.accountSummary()
        data = {item.tag: float(item.value) for item in summary if item.value is not None}
        cash = data.get("TotalCashValue", 0.0)
        total = data.get("NetLiquidation", cash)
        return AccountInfo(
            account_id=self.config.account or "ib",
            cash=cash,
            total_value=total,
            available=data.get("AvailableFunds", cash),
        )
    
    def query_positions(self) -> Dict[str, PositionInfo]:
        if not self._ib:
            raise RuntimeError("IB client not connected")
        results: Dict[str, PositionInfo] = {}
        for pos in self._ib.positions():
            symbol = pos.contract.symbol
            results[symbol] = PositionInfo(
                symbol=symbol,
                size=float(pos.position),
                avg_price=float(pos.avgCost),
                market_value=float(pos.marketValue or 0.0) if hasattr(pos, "marketValue") else 0.0,
                unrealized_pnl=float(pos.unrealizedPNL or 0.0) if hasattr(pos, "unrealizedPNL") else 0.0,
            )
        return results


# ---------------------------------------------------------------------------
# Unified Trading Gateway
# ---------------------------------------------------------------------------

class TradingGateway:
    """
    统一交易网关 - 支持模拟和实盘交易的统一接口
    
    Features:
    - 模式切换: BACKTEST / PAPER / LIVE
    - 多经纪商支持: 东方财富、富途、雪球、IBKR
    - 统一下单接口: buy/sell/cancel
    - 账户查询: 资金、持仓、订单
    - 风控集成: 可选启用风控检查
    
    Usage:
        >>> # 模拟交易
        >>> gateway = TradingGateway.create_paper(initial_cash=1000000)
        >>> gateway.connect()
        >>> 
        >>> order_id = gateway.buy("600519.SH", 100, price=1800.0)
        >>> gateway.sell("600519.SH", 50, price=1850.0)
        >>> 
        >>> account = gateway.get_account()
        >>> positions = gateway.get_positions()
        >>> 
        >>> # 实盘交易 (需要实现对应适配器)
        >>> gateway = TradingGateway.create_live(
        ...     broker=BrokerType.FUTU,
        ...     host="127.0.0.1",
        ...     port=11111
        ... )
    """
    
    def __init__(
        self,
        config: Optional[GatewayConfig] = None,
        event_engine: Optional[EventEngine] = None,
        risk_manager = None,
        authorizer: Optional[Authorizer] = None,
        audit_logger: Optional[AuditLogger] = None,
        tenant_id: str = "",
    ):
        """
        Initialize trading gateway.
        
        Args:
            config: Gateway configuration
            event_engine: Event engine for publishing events
            risk_manager: Optional risk manager for pre-trade checks
        """
        self.config = config or GatewayConfig()
        self.event_engine = event_engine
        self.risk_manager = risk_manager
        self.authorizer = authorizer
        self.audit_logger = audit_logger
        self.tenant_id = tenant_id
        
        self._status = GatewayStatus.DISCONNECTED
        self._adapter = self._create_adapter()
        
        # Callbacks
        self._order_callbacks: List[Callable[[OrderInfo], None]] = []
        self._trade_callbacks: List[Callable[[TradeInfo], None]] = []
    
    @classmethod
    def create_paper(
        cls,
        initial_cash: float = 1_000_000.0,
        commission_rate: float = 0.0003,
        slippage: float = 0.0001,
        event_engine: Optional[EventEngine] = None
    ) -> "TradingGateway":
        """Create paper trading gateway."""
        config = GatewayConfig(
            mode=TradingMode.PAPER,
            broker=BrokerType.PAPER,
            initial_cash=initial_cash,
            commission_rate=commission_rate,
            slippage=slippage
        )
        return cls(config, event_engine)
    
    @classmethod
    def create_live(
        cls,
        broker: BrokerType,
        event_engine: Optional[EventEngine] = None,
        **kwargs
    ) -> "TradingGateway":
        """Create live trading gateway."""
        config = GatewayConfig(
            mode=TradingMode.LIVE,
            broker=broker,
            **kwargs
        )
        return cls(config, event_engine)
    
    def _create_adapter(self):
        """Create appropriate adapter based on config."""
        broker = self.config.broker
        gateway_provider = _normalize_provider(self.config.gateway_provider)

        if broker == BrokerType.PAPER:
            return PaperTradingAdapter(self.config)
        elif gateway_provider == "vnpy":
            return VnpyGatewayAdapter(self.config)
        elif broker == BrokerType.EASTMONEY:
            return EastMoneyAdapter(self.config)
        elif broker == BrokerType.FUTU:
            return FutuAdapter(self.config)
        elif broker == BrokerType.XUEQIU:
            return XueqiuAdapter(self.config)
        elif broker == BrokerType.IB:
            return IBAdapter(self.config)
        elif broker in {BrokerType.QMT, BrokerType.XTQUANT}:
            qmt_provider = _normalize_provider(self.config.qmt_provider)
            if gateway_provider in {"third_party", "vnpy"} and qmt_provider == "self":
                qmt_provider = gateway_provider
            if qmt_provider not in QMT_PROVIDER_REGISTRY:
                available = ", ".join(available_qmt_providers())
                raise ValueError(f"Unsupported QMT provider: {qmt_provider}. Available: {available}")
            return QMT_PROVIDER_REGISTRY[qmt_provider](self.config)
        elif broker in {BrokerType.CTP, BrokerType.VNPY, BrokerType.VNPY_QMT}:
            return VnpyGatewayAdapter(self.config)
        elif broker == BrokerType.XTP:
            return XtpAdapter(self.config)
        elif broker == BrokerType.HUNDSUN:
            return HundsunUftAdapter(self.config)
        else:
            raise ValueError(f"Unsupported broker: {broker}")
    
    # ---------------------------------------------------------------------------
    # Connection Management
    # ---------------------------------------------------------------------------
    
    def connect(self) -> bool:
        """Connect to broker."""
        logger.info(
            "Connecting trading gateway",
            mode=self.config.mode.value,
            broker=self.config.broker.value
        )
        
        self._status = GatewayStatus.CONNECTING
        
        try:
            result = self._adapter.connect()
            if result:
                self._status = GatewayStatus.CONNECTED
                self._publish_event("gateway.connected", {"broker": self.config.broker.value})
            else:
                self._status = GatewayStatus.ERROR
            return result
        except Exception as e:
            logger.error("Connection failed", error=str(e))
            self._status = GatewayStatus.ERROR
            return False
    
    def disconnect(self) -> None:
        """Disconnect from broker."""
        self._adapter.disconnect()
        self._status = GatewayStatus.DISCONNECTED
        self._publish_event("gateway.disconnected", {"broker": self.config.broker.value})
    
    def is_connected(self) -> bool:
        return self._adapter.is_connected()
    
    @property
    def status(self) -> GatewayStatus:
        return self._status
    
    # ---------------------------------------------------------------------------
    # Order Management
    # ---------------------------------------------------------------------------
    
    def buy(
        self,
        symbol: str,
        quantity: float,
        price: Optional[float] = None,
        order_type: OrderTypeEnum = OrderTypeEnum.LIMIT,
        subject: Optional[Subject] = None,
    ) -> str:
        """
        Submit buy order.
        
        Args:
            symbol: Symbol to buy
            quantity: Number of shares
            price: Limit price (None for market order)
            order_type: Order type
            
        Returns:
            Order ID
        """
        return self._submit_order(symbol, Side.BUY, quantity, price, order_type, subject=subject)
    
    def sell(
        self,
        symbol: str,
        quantity: float,
        price: Optional[float] = None,
        order_type: OrderTypeEnum = OrderTypeEnum.LIMIT,
        subject: Optional[Subject] = None,
    ) -> str:
        """
        Submit sell order.
        
        Args:
            symbol: Symbol to sell
            quantity: Number of shares
            price: Limit price (None for market order)
            order_type: Order type
            
        Returns:
            Order ID
        """
        return self._submit_order(symbol, Side.SELL, quantity, price, order_type, subject=subject)
    
    def cancel(self, order_id: str, subject: Optional[Subject] = None) -> bool:
        """Cancel order."""
        self._authorize(Permission.ORDER_CANCEL, subject, ResourceScope(tenant_id=self.tenant_id))
        result = self._adapter.cancel_order(order_id)
        if result:
            self._publish_event("order.cancelled", {"order_id": order_id})
            self._audit("order.cancel", subject, {"order_id": order_id}, result="ok")
        return result
    
    def _submit_order(
        self,
        symbol: str,
        side: Side,
        quantity: float,
        price: Optional[float],
        order_type: OrderTypeEnum,
        subject: Optional[Subject] = None,
    ) -> str:
        """Internal order submission with risk checks."""
        # Risk check (if enabled)
        if self.risk_manager and self.config.enable_risk_check:
            if price is None and order_type == OrderTypeEnum.MARKET:
                logger.warning("Risk check skipped for market order without price", symbol=symbol)
            else:
                account = self.get_account()
                positions = self.get_positions()
                result = self.risk_manager.check_order(
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    price=price or 0.0,
                    account=account,
                    positions=positions,
                )
                if not result.passed:
                    raise PermissionError(f"Risk check failed: {result.reason}")

        self._authorize(Permission.ORDER_SUBMIT, subject, ResourceScope(tenant_id=self.tenant_id))
        
        # Submit to adapter
        order_id = self._adapter.submit_order(symbol, side, quantity, price, order_type)
        
        self._publish_event("order.submitted", {
            "order_id": order_id,
            "symbol": symbol,
            "side": side.value,
            "quantity": quantity,
            "price": price
        })
        self._audit("order.submit", subject, {"order_id": order_id, "symbol": symbol}, result="ok")
        
        return order_id
    
    # ---------------------------------------------------------------------------
    # Query
    # ---------------------------------------------------------------------------
    
    def get_order(self, order_id: str) -> Optional[OrderInfo]:
        """Get order by ID."""
        return self._adapter.query_order(order_id)
    
    def get_account(self) -> AccountInfo:
        """Get account information."""
        return self._adapter.query_account()
    
    def get_positions(self) -> Dict[str, PositionInfo]:
        """Get all positions."""
        return self._adapter.query_positions()

    def get_position(self, symbol: str) -> Optional[PositionInfo]:
        """Get position for a symbol."""
        positions = self._adapter.query_positions()
        return positions.get(symbol)

    def get_orders(self, symbol: Optional[str] = None) -> List[OrderInfo]:
        """Get cached orders when supported by the underlying adapter."""
        query_orders = getattr(self._adapter, "query_orders", None)
        if callable(query_orders):
            return query_orders(symbol=symbol)
        return []

    def get_trades(
        self,
        *,
        symbol: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[TradeInfo]:
        """Get recent trades when supported by the underlying adapter."""
        query_trades = getattr(self._adapter, "query_trades", None)
        if callable(query_trades):
            return query_trades(symbol=symbol, limit=limit)
        return []
    
    # ---------------------------------------------------------------------------
    # Price Updates (for paper trading)
    # ---------------------------------------------------------------------------
    
    def update_price(self, symbol: str, price: float) -> None:
        """
        Update market price (for paper trading order matching).
        
        Args:
            symbol: Symbol
            price: Current price
        """
        if isinstance(self._adapter, PaperTradingAdapter):
            self._adapter.update_price(symbol, price)
    
    # ---------------------------------------------------------------------------
    # Callbacks
    # ---------------------------------------------------------------------------
    
    def on_order(self, callback: Callable[[OrderInfo], None]) -> None:
        """Register order update callback."""
        self._order_callbacks.append(callback)
    
    def on_trade(self, callback: Callable[[TradeInfo], None]) -> None:
        """Register trade callback."""
        self._trade_callbacks.append(callback)
    
    # ---------------------------------------------------------------------------
    # Events
    # ---------------------------------------------------------------------------
    
    def _publish_event(self, event_type: str, data: Any) -> None:
        """Publish event if event engine is available."""
        if self.event_engine:
            self.event_engine.put(Event(event_type, data))

    def _authorize(self, permission: str, subject: Optional[Subject], scope: ResourceScope) -> None:
        if self.authorizer:
            self.authorizer.require(permission, subject, scope)

    def _audit(self, action: str, subject: Optional[Subject], details: Dict[str, Any], result: str) -> None:
        actor = subject.subject_id if subject else "system"
        audit_event(
            self.audit_logger,
            actor=actor,
            action=action,
            resource="gateway",
            result=result,
            details=details,
        )

    # ---------------------------------------------------------------------------
    # Snapshot / Restore
    # ---------------------------------------------------------------------------

    def snapshot_state(self) -> Dict[str, Any]:
        if hasattr(self._adapter, "snapshot_state"):
            return self._adapter.snapshot_state()
        return {}

    def restore_state(self, payload: Dict[str, Any]) -> None:
        if hasattr(self._adapter, "restore_state"):
            self._adapter.restore_state(payload)


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", ""))
    except ValueError:
        return None


def _map_live_order_status(status: str) -> OrderStatusEnum:
    mapping = {
        "pending_submit": OrderStatusEnum.PENDING,
        "submitted": OrderStatusEnum.SUBMITTED,
        "partial_fill": OrderStatusEnum.PARTIAL,
        "filled": OrderStatusEnum.FILLED,
        "cancel_pending": OrderStatusEnum.PENDING,
        "cancelled": OrderStatusEnum.CANCELLED,
        "rejected": OrderStatusEnum.REJECTED,
        "expired": OrderStatusEnum.CANCELLED,
        "error": OrderStatusEnum.REJECTED,
    }
    return mapping.get(status, OrderStatusEnum.PENDING)


def _enum_token(value: Any) -> str:
    if isinstance(value, Enum):
        return value.name.upper()
    name = getattr(value, "name", None)
    if name:
        return str(name).upper()
    raw = getattr(value, "value", value)
    return str(raw).upper()


def _optional_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _float_attr(obj: Any, *names: str) -> float:
    for name in names:
        value = getattr(obj, name, None)
        if value in (None, ""):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def _normalize_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return _parse_dt(value)
    return None


def _map_vnpy_order_status(status: Any) -> OrderStatusEnum:
    token = _enum_token(status)
    mapping = {
        "SUBMITTING": OrderStatusEnum.PENDING,
        "NOTTRADED": OrderStatusEnum.SUBMITTED,
        "PARTTRADED": OrderStatusEnum.PARTIAL,
        "ALLTRADED": OrderStatusEnum.FILLED,
        "CANCELLED": OrderStatusEnum.CANCELLED,
        "REJECTED": OrderStatusEnum.REJECTED,
        "PENDING": OrderStatusEnum.PENDING,
        "SUBMITTED": OrderStatusEnum.SUBMITTED,
        "PARTIAL": OrderStatusEnum.PARTIAL,
        "FILLED": OrderStatusEnum.FILLED,
    }
    return mapping.get(token, OrderStatusEnum.PENDING)


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    'TradingGateway',
    'TradingMode',
    'GatewayStatus',
    'BrokerType',
    'GatewayConfig',
    'PaperTradingAdapter',
    'EastMoneyAdapter',
    'FutuAdapter',
    'XueqiuAdapter',
    'IBAdapter',
    'XtQuantAdapter',
    'XtpAdapter',
    'HundsunUftAdapter',
    'VnpyGatewayAdapter',
    'available_qmt_providers',
    'register_qmt_provider',
]
