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
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol

from src.core.events import EventEngine, Event, EventType
from src.core.interfaces import (
    AccountInfo, OrderInfo, PositionInfo, TradeInfo,
    Side, OrderTypeEnum, OrderStatusEnum
)
from src.core.logger import get_logger
from src.core.audit import AuditLogger, audit_event
from src.core.auth import Authorizer, Permission, ResourceScope, Subject

logger = get_logger("trading_gateway")


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
        # TODO: Implement actual connection
        # import easytrader
        # self._client = easytrader.use('universal_client')
        # self._client.connect(exe_path=..., tesseract_cmd=...)
        raise NotImplementedError("EastMoney adapter not implemented. Install easytrader first.")
    
    def disconnect(self) -> None:
        self._connected = False
    
    def is_connected(self) -> bool:
        return self._connected
    
    def submit_order(self, symbol: str, side: Side, quantity: float, 
                     price: Optional[float] = None, order_type: OrderTypeEnum = OrderTypeEnum.LIMIT) -> str:
        raise NotImplementedError()
    
    def cancel_order(self, order_id: str) -> bool:
        raise NotImplementedError()
    
    def query_order(self, order_id: str) -> Optional[OrderInfo]:
        raise NotImplementedError()
    
    def query_account(self) -> AccountInfo:
        raise NotImplementedError()
    
    def query_positions(self) -> Dict[str, PositionInfo]:
        raise NotImplementedError()


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
        # TODO: Implement actual connection
        # from futu import OpenSecTradeContext
        # self._ctx = OpenSecTradeContext(host=config.host, port=config.port)
        raise NotImplementedError("Futu adapter not implemented. Install futu-api first.")
    
    def disconnect(self) -> None:
        self._connected = False
    
    def is_connected(self) -> bool:
        return self._connected
    
    def submit_order(self, symbol: str, side: Side, quantity: float,
                     price: Optional[float] = None, order_type: OrderTypeEnum = OrderTypeEnum.LIMIT) -> str:
        raise NotImplementedError()
    
    def cancel_order(self, order_id: str) -> bool:
        raise NotImplementedError()
    
    def query_order(self, order_id: str) -> Optional[OrderInfo]:
        raise NotImplementedError()
    
    def query_account(self) -> AccountInfo:
        raise NotImplementedError()
    
    def query_positions(self) -> Dict[str, PositionInfo]:
        raise NotImplementedError()


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
        raise NotImplementedError("Xueqiu adapter not implemented.")
    
    def disconnect(self) -> None:
        self._connected = False
    
    def is_connected(self) -> bool:
        return self._connected
    
    def submit_order(self, symbol: str, side: Side, quantity: float,
                     price: Optional[float] = None, order_type: OrderTypeEnum = OrderTypeEnum.LIMIT) -> str:
        raise NotImplementedError()
    
    def cancel_order(self, order_id: str) -> bool:
        raise NotImplementedError()
    
    def query_order(self, order_id: str) -> Optional[OrderInfo]:
        raise NotImplementedError()
    
    def query_account(self) -> AccountInfo:
        raise NotImplementedError()
    
    def query_positions(self) -> Dict[str, PositionInfo]:
        raise NotImplementedError()


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
    
    def connect(self) -> bool:
        logger.info("Connecting to Interactive Brokers...")
        # TODO: Implement actual connection
        # from ib_insync import IB
        # self._ib = IB()
        # self._ib.connect(host=config.host, port=config.port, clientId=1)
        raise NotImplementedError("IB adapter not implemented. Install ib_insync first.")
    
    def disconnect(self) -> None:
        self._connected = False
    
    def is_connected(self) -> bool:
        return self._connected
    
    def submit_order(self, symbol: str, side: Side, quantity: float,
                     price: Optional[float] = None, order_type: OrderTypeEnum = OrderTypeEnum.LIMIT) -> str:
        raise NotImplementedError()
    
    def cancel_order(self, order_id: str) -> bool:
        raise NotImplementedError()
    
    def query_order(self, order_id: str) -> Optional[OrderInfo]:
        raise NotImplementedError()
    
    def query_account(self) -> AccountInfo:
        raise NotImplementedError()
    
    def query_positions(self) -> Dict[str, PositionInfo]:
        raise NotImplementedError()


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
        
        if broker == BrokerType.PAPER:
            return PaperTradingAdapter(self.config)
        elif broker == BrokerType.EASTMONEY:
            return EastMoneyAdapter(self.config)
        elif broker == BrokerType.FUTU:
            return FutuAdapter(self.config)
        elif broker == BrokerType.XUEQIU:
            return XueqiuAdapter(self.config)
        elif broker == BrokerType.IB:
            return IBAdapter(self.config)
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
            # TODO: Integrate with risk manager
            pass

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
]
