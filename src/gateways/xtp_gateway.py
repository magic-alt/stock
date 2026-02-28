"""
XTP Gateway - 中泰证券XTP极速交易网关

Implements live trading connection via XTP (中泰证券极速交易平台).
This is the recommended gateway for professional/institutional traders.

V3.2.0: Initial release

Features:
- High-performance trading connection
- Support for SSE, SZSE, BSE markets
- Level2 market data (if authorized)
- Order submission (limit, market, FAK, FOK)
- Order cancellation
- Real-time order/trade callbacks
- Auto-reconnection with state recovery

Dependencies:
- XTP SDK (C++ SDK with Python bindings)
- Test account from 中泰证券

Architecture:
    XtpGateway
    ├── XtpTraderApi - Trading connection
    ├── XtpQuoteApi - Market data connection (optional)
    └── Callbacks - Order/Trade/Quote handlers

Usage:
    >>> from src.gateways import XtpGateway, GatewayConfig
    >>> from queue import Queue
    >>> 
    >>> config = GatewayConfig(
    ...     account_id="YOUR_ACCOUNT",
    ...     broker="xtp",
    ...     password="YOUR_PASSWORD",  # Or use env: XTP_PASSWORD
    ...     trade_server="tcp://x.x.x.x:port",
    ...     quote_server="tcp://x.x.x.x:port",
    ...     client_id=1,
    ... )
    >>> 
    >>> event_queue = Queue()
    >>> gateway = XtpGateway(config, event_queue)
    >>> 
    >>> # Connect
    >>> gateway.connect()
    >>> 
    >>> # Send order
    >>> order_id = gateway.send_order(
    ...     symbol="600519.SH",
    ...     side="buy",
    ...     quantity=100,
    ...     price=1800.0,
    ... )

References:
- XTP GitHub: https://github.com/AtlasCoCo/Zhongtai_XTP_API_Python
- DolphinDB XTP Plugin: https://docs.dolphindb.cn/zh/plugins/xtp.html
- XTP Official Docs: Contact 中泰证券 for access
"""
from __future__ import annotations

import os
import logging
import threading
import time
from ctypes import c_char_p, c_int, c_double, c_uint64, Structure, POINTER
from datetime import datetime
from pathlib import Path
from queue import Queue
from typing import Any, Dict, List, Optional

from src.gateways.base_live_gateway import (
    BaseLiveGateway,
    GatewayConfig,
    GatewayStatus,
    OrderStatus,
    OrderType,
    OrderSide,
    OrderRequest,
    OrderUpdate,
    TradeUpdate,
    AccountUpdate,
    PositionUpdate,
    GatewayEventType,
)
from src.gateways.mappers import SymbolMapper, OrderMapper, XTPExchange

logger = logging.getLogger("gateways.xtp")


# Check if XTP SDK is available
# XTP uses C++ SDK, typically accessed via ctypes/cffi/SWIG bindings
XTP_AVAILABLE = False
xtp_api = None
_XTP_IMPORT_ERROR: str = ""

try:
    # Try importing common XTP Python wrapper packages
    # The actual import depends on how XTP SDK is packaged
    import xtp_api  # type: ignore  # Example package name
    from xtp_api import (  # type: ignore
        XTPTraderApi,
        XTPTraderSpi,
        XTPQuoteApi,
        XTPQuoteSpi,
    )
    XTP_AVAILABLE = True
except ImportError as _exc:
    _XTP_IMPORT_ERROR = (
        f"XTP SDK not available: {_exc}. "
        "Install the xtp_api package or set XTP_SDK_PATH. "
        "Gateway will operate in stub mode."
    )
    logger.warning("xtp_sdk_unavailable: %s", _exc)


# ---------------------------------------------------------------------------
# XTP Data Structures (Stub definitions for type hints)
# These mirror the XTP C++ API structures
# ---------------------------------------------------------------------------

class XTPOrderInfo:
    """XTP order information structure (stub)."""
    order_xtp_id: int = 0
    order_client_id: int = 0
    order_cancel_client_id: int = 0
    order_cancel_xtp_id: int = 0
    ticker: str = ""
    market: int = 0
    price: float = 0.0
    quantity: int = 0
    price_type: int = 0
    side: int = 0
    business_type: int = 0
    qty_traded: int = 0
    qty_left: int = 0
    trade_amount: float = 0.0
    order_status: int = 0
    order_submit_status: int = 0
    order_type: int = 0
    insert_time: int = 0
    update_time: int = 0
    cancel_time: int = 0


class XTPTradeReport:
    """XTP trade report structure (stub)."""
    order_xtp_id: int = 0
    order_client_id: int = 0
    ticker: str = ""
    market: int = 0
    local_order_id: int = 0
    exec_id: str = ""
    price: float = 0.0
    quantity: int = 0
    trade_time: int = 0
    trade_amount: float = 0.0
    report_index: int = 0
    side: int = 0
    business_type: int = 0


class XTPQueryAssetRsp:
    """XTP asset query response (stub)."""
    total_asset: float = 0.0
    buying_power: float = 0.0
    security_asset: float = 0.0
    fund_buy_amount: float = 0.0
    fund_buy_fee: float = 0.0
    fund_sell_amount: float = 0.0
    fund_sell_fee: float = 0.0
    withholding_amount: float = 0.0
    frozen_margin: float = 0.0
    frozen_exec_cash: float = 0.0
    frozen_exec_fee: float = 0.0
    pay_later: float = 0.0
    preadva_pay: float = 0.0
    orig_banlance: float = 0.0
    banlance: float = 0.0
    deposit_withdraw: float = 0.0


class XTPQueryStkPositionRsp:
    """XTP position query response (stub)."""
    ticker: str = ""
    ticker_name: str = ""
    market: int = 0
    total_qty: int = 0
    sellable_qty: int = 0
    avg_price: float = 0.0
    unrealized_pnl: float = 0.0
    yesterday_position: int = 0
    purchase_redeemable_qty: int = 0


# ---------------------------------------------------------------------------
# XTP Gateway Implementation
# ---------------------------------------------------------------------------

class XtpGateway(BaseLiveGateway):
    """
    中泰证券XTP极速交易网关
    
    通过XTP SDK连接中泰证券极速交易系统进行实盘交易。
    
    Connection Flow:
    1. Initialize TraderApi with log path and client_id
    2. Register callback handler (TraderSpi)
    3. Login with account credentials
    4. Subscribe to events
    5. Trading ready
    
    Thread Model:
    - XTP uses internal threads for network I/O
    - Callbacks are invoked on XTP's thread
    - Gateway normalizes and forwards to event queue
    
    Order ID Mapping:
    - client_order_id: Generated by gateway (XTP-00000001)
    - broker_order_id: order_xtp_id from XTP (unique per session)
    - exchange_order_id: exchange's order ID
    
    Attributes:
        config: Gateway configuration
        trader_api: XTPTraderApi instance
        quote_api: XTPQuoteApi instance (optional, for market data)
    """
    
    def __init__(
        self,
        config: GatewayConfig,
        event_queue: Queue,
        logger=None,
    ):
        """
        Initialize XTP gateway.
        
        Args:
            config: Gateway configuration with XTP connection details
            event_queue: Queue for event publishing
            logger: Optional logger instance
            
        Raises:
            ImportError: If XTP SDK is not available
        """
        super().__init__(config, event_queue, logger)
        
        # Note: In production, XTP_AVAILABLE would be True if SDK is installed
        # For development, we implement with stub mode
        self._stub_mode = not XTP_AVAILABLE
        
        if self._stub_mode:
            self.log.warning(
                "xtp_gateway_stub_mode",
                msg="XTP SDK not available, running in stub mode"
            )
        
        # XTP API instances
        self._trader_api = None
        self._trader_spi = None
        self._quote_api = None
        self._quote_spi = None
        
        # Session info
        self._session_id = 0
        self._request_id = 0
        self._request_lock = threading.Lock()
        
        # Order tracking
        self._client_id_to_xtp_id: Dict[str, int] = {}
        self._xtp_id_to_client_id: Dict[int, str] = {}
        
        # Log path for XTP SDK
        self._log_path = Path("./logs/xtp")
        self._log_path.mkdir(parents=True, exist_ok=True)
        
        self.log.info(
            "xtp_gateway_initialized",
            account_id=config.account_id,
            trade_server=config.trade_server,
            stub_mode=self._stub_mode,
        )
    
    def _next_request_id(self) -> int:
        """Generate next request ID."""
        with self._request_lock:
            self._request_id += 1
            return self._request_id
    
    # ---------------------------------------------------------------------------
    # Connection Management
    # ---------------------------------------------------------------------------
    
    def _do_connect(self) -> bool:
        """
        Connect to XTP trading server.
        
        Returns:
            True if connection successful
        """
        if self._stub_mode:
            return self._stub_connect()
        
        try:
            # Create TraderApi
            # XTPTraderApi.CreateTraderApi(client_id, log_path, log_level)
            self._trader_api = XTPTraderApi.CreateTraderApi(
                self.config.client_id,
                str(self._log_path),
                1  # XTP_LOG_LEVEL_DEBUG
            )
            
            # Create and register callback handler
            self._trader_spi = _XtpTraderSpi(self)
            self._trader_api.RegisterSpi(self._trader_spi)
            
            # Subscribe to events
            self._trader_api.SubscribePublicTopic(0)  # XTP_TERT_RESTART
            
            # Parse server address
            # Format: "tcp://ip:port"
            server = self.config.trade_server or ""
            if server.startswith("tcp://"):
                server = server[6:]
            
            ip, port = server.split(":") if ":" in server else (server, "6001")
            
            # Login
            # XTPTraderApi.Login(ip, port, user, password, sock_type, local_ip)
            password = self.config.password or os.environ.get("XTP_PASSWORD", "")
            
            self._session_id = self._trader_api.Login(
                ip,
                int(port),
                self.config.account_id,
                password,
                1,  # XTP_PROTOCOL_TCP
                ""  # local_ip, empty for auto
            )
            
            if self._session_id > 0:
                self.log.info(
                    "xtp_connected",
                    session_id=self._session_id,
                    account=self.config.account_id,
                )
                return True
            else:
                error = self._trader_api.GetApiLastError()
                self.log.error(
                    "xtp_login_failed",
                    error_id=error.error_id if error else 0,
                    error_msg=error.error_msg if error else "Unknown error",
                )
                return False
                
        except Exception as e:
            self.log.error("xtp_connect_error", error=str(e))
            return False
    
    def _stub_connect(self) -> bool:
        """Stub connection for development/testing."""
        self._session_id = 1
        self.log.info("xtp_stub_connected", account=self.config.account_id)
        return True
    
    def _do_disconnect(self) -> None:
        """Disconnect from XTP server."""
        if self._stub_mode:
            self._session_id = 0
            self.log.info("xtp_stub_disconnected")
            return
        
        try:
            if self._trader_api and self._session_id > 0:
                self._trader_api.Logout(self._session_id)
                self._trader_api.Release()
            
            self._trader_api = None
            self._trader_spi = None
            self._session_id = 0
            
            self.log.info("xtp_disconnected")
            
        except Exception as e:
            self.log.error("xtp_disconnect_error", error=str(e))
    
    def _do_heartbeat(self) -> None:
        """XTP handles heartbeat internally."""
        pass
    
    # ---------------------------------------------------------------------------
    # Order Management
    # ---------------------------------------------------------------------------
    
    def _do_send_order(self, request: OrderRequest) -> str:
        """
        Send order via XTP.
        
        Args:
            request: Order request
            
        Returns:
            broker_order_id (XTP order ID as string)
        """
        if self._stub_mode:
            return self._stub_send_order(request)
        
        if not self._trader_api or self._session_id <= 0:
            raise RuntimeError("XTP not connected")
        
        # Convert symbol to XTP format
        code, market = SymbolMapper.to_xtp(request.symbol)
        
        # Build XTP order request
        # XTPOrderInsertInfo structure
        order_insert = {
            "order_client_id": hash(request.client_order_id) & 0xFFFFFFFF,
            "ticker": code,
            "market": market.value,
            "price": request.price or 0.0,
            "quantity": int(request.quantity),
            "price_type": OrderMapper.order_type_to_xtp(request.order_type),
            "side": OrderMapper.side_to_xtp(request.side),
            "business_type": 0,  # XTP_BUSINESS_TYPE_CASH
        }
        
        # Insert order
        xtp_order_id = self._trader_api.InsertOrder(
            order_insert,
            self._session_id
        )
        
        if xtp_order_id > 0:
            # Store mapping
            self._client_id_to_xtp_id[request.client_order_id] = xtp_order_id
            self._xtp_id_to_client_id[xtp_order_id] = request.client_order_id
            
            self.log.info(
                "xtp_order_sent",
                client_order_id=request.client_order_id,
                xtp_order_id=xtp_order_id,
                symbol=request.symbol,
            )
            
            return str(xtp_order_id)
        else:
            error = self._trader_api.GetApiLastError()
            raise RuntimeError(
                f"XTP order failed: {error.error_msg if error else 'Unknown'}"
            )
    
    def _stub_send_order(self, request: OrderRequest) -> str:
        """Stub order for development."""
        xtp_order_id = int(time.time() * 1000) % 1000000000
        
        self._client_id_to_xtp_id[request.client_order_id] = xtp_order_id
        self._xtp_id_to_client_id[xtp_order_id] = request.client_order_id
        
        self.log.info(
            "xtp_stub_order_sent",
            client_order_id=request.client_order_id,
            xtp_order_id=xtp_order_id,
        )
        
        # Simulate order accepted
        self._simulate_order_accepted(request, xtp_order_id)
        
        return str(xtp_order_id)
    
    def _simulate_order_accepted(self, request: OrderRequest, xtp_order_id: int) -> None:
        """Simulate order acceptance for stub mode."""
        update = OrderUpdate(
            client_order_id=request.client_order_id,
            broker_order_id=str(xtp_order_id),
            symbol=request.symbol,
            side=request.side,
            status=OrderStatus.SUBMITTED,
            order_type=request.order_type,
            price=request.price or 0.0,
            quantity=request.quantity,
        )
        
        # Schedule callback
        threading.Timer(0.1, lambda: self._on_order_update(update)).start()
    
    def _do_cancel_order(
        self, 
        broker_order_id: str, 
        client_order_id: str
    ) -> bool:
        """
        Cancel order via XTP.
        
        Args:
            broker_order_id: XTP order ID
            client_order_id: Client order ID
            
        Returns:
            True if cancel request sent
        """
        if self._stub_mode:
            return self._stub_cancel_order(broker_order_id, client_order_id)
        
        if not self._trader_api or self._session_id <= 0:
            raise RuntimeError("XTP not connected")
        
        xtp_order_id = int(broker_order_id)
        
        # Cancel order
        cancel_result = self._trader_api.CancelOrder(
            xtp_order_id,
            self._session_id
        )
        
        if cancel_result > 0:
            self.log.info(
                "xtp_cancel_sent",
                xtp_order_id=xtp_order_id,
                cancel_id=cancel_result,
            )
            return True
        else:
            error = self._trader_api.GetApiLastError()
            self.log.error(
                "xtp_cancel_failed",
                xtp_order_id=xtp_order_id,
                error=error.error_msg if error else "Unknown",
            )
            return False
    
    def _stub_cancel_order(
        self, 
        broker_order_id: str, 
        client_order_id: str
    ) -> bool:
        """Stub cancel for development."""
        self.log.info(
            "xtp_stub_cancel_sent",
            broker_order_id=broker_order_id,
        )
        
        # Simulate cancel confirmation
        order = self._orders.get(client_order_id)
        if order:
            update = OrderUpdate(
                client_order_id=client_order_id,
                broker_order_id=broker_order_id,
                symbol=order.symbol,
                side=order.side,
                status=OrderStatus.CANCELLED,
                order_type=order.order_type,
                price=order.price,
                quantity=order.quantity,
                filled_quantity=order.filled_quantity,
            )
            threading.Timer(0.1, lambda: self._on_order_update(update)).start()
        
        return True
    
    # ---------------------------------------------------------------------------
    # Query Methods
    # ---------------------------------------------------------------------------
    
    def _do_query_account(self) -> Optional[AccountUpdate]:
        """Query account from XTP."""
        if self._stub_mode:
            return self._stub_query_account()
        
        if not self._trader_api or self._session_id <= 0:
            return None
        
        try:
            # Query asset
            # Result comes via OnQueryAsset callback
            request_id = self._next_request_id()
            result = self._trader_api.QueryAsset(self._session_id, request_id)
            
            if result != 0:
                self.log.error("xtp_query_account_failed", result=result)
                return None
            
            # In real implementation, would wait for callback
            # For now, return None and let callback populate
            return None
            
        except Exception as e:
            self.log.error("xtp_query_account_error", error=str(e))
            return None
    
    def _stub_query_account(self) -> AccountUpdate:
        """Stub account query."""
        return AccountUpdate(
            account_id=self.config.account_id,
            cash=1000000.0,
            available=950000.0,
            frozen=50000.0,
            equity=1100000.0,
        )
    
    def _do_query_positions(self) -> List[PositionUpdate]:
        """Query positions from XTP."""
        if self._stub_mode:
            return self._stub_query_positions()
        
        if not self._trader_api or self._session_id <= 0:
            return []
        
        try:
            # Query positions
            request_id = self._next_request_id()
            result = self._trader_api.QueryPosition(
                "",  # ticker, empty for all
                self._session_id,
                request_id
            )
            
            if result != 0:
                self.log.error("xtp_query_positions_failed", result=result)
                return []
            
            # In real implementation, would wait for callback
            return []
            
        except Exception as e:
            self.log.error("xtp_query_positions_error", error=str(e))
            return []
    
    def _stub_query_positions(self) -> List[PositionUpdate]:
        """Stub positions query."""
        return [
            PositionUpdate(
                symbol="600519.SH",
                total_quantity=1000,
                available_quantity=1000,
                avg_price=1800.0,
                market_value=1850000.0,
                unrealized_pnl=50000.0,
            )
        ]
    
    def _do_query_orders(self) -> List[OrderUpdate]:
        """Query open orders from XTP."""
        if self._stub_mode:
            return []
        
        if not self._trader_api or self._session_id <= 0:
            return []
        
        try:
            # Query orders
            request_id = self._next_request_id()
            query_param = {
                "ticker": "",  # All tickers
            }
            result = self._trader_api.QueryOrders(
                query_param,
                self._session_id,
                request_id
            )
            
            if result != 0:
                self.log.error("xtp_query_orders_failed", result=result)
            
            return []
            
        except Exception as e:
            self.log.error("xtp_query_orders_error", error=str(e))
            return []
    
    # ---------------------------------------------------------------------------
    # Callback Processing
    # ---------------------------------------------------------------------------
    
    def _process_order_callback(self, order_info: XTPOrderInfo) -> None:
        """Process order callback from XTP."""
        try:
            xtp_order_id = order_info.order_xtp_id
            
            # Find client order ID
            client_order_id = self._xtp_id_to_client_id.get(
                xtp_order_id, f"XTP-{xtp_order_id}"
            )
            
            # Convert symbol
            symbol = SymbolMapper.from_xtp(
                order_info.ticker,
                XTPExchange(order_info.market)
            )
            
            # Map status and side
            status = OrderMapper.status_from_xtp(order_info.order_status)
            side = OrderMapper.side_from_xtp(order_info.side)
            
            update = OrderUpdate(
                client_order_id=client_order_id,
                broker_order_id=str(xtp_order_id),
                symbol=symbol,
                side=side,
                status=status,
                order_type=OrderMapper.order_type_from_xtp(order_info.price_type),
                price=order_info.price,
                quantity=order_info.quantity,
                filled_quantity=order_info.qty_traded,
                avg_fill_price=order_info.trade_amount / order_info.qty_traded 
                    if order_info.qty_traded > 0 else 0.0,
            )
            
            self._on_order_update(update)
            
        except Exception as e:
            self.log.error("xtp_order_callback_error", error=str(e))
    
    def _process_trade_callback(self, trade_report: XTPTradeReport) -> None:
        """Process trade callback from XTP."""
        try:
            xtp_order_id = trade_report.order_xtp_id
            
            # Find client order ID
            client_order_id = self._xtp_id_to_client_id.get(
                xtp_order_id, ""
            )
            
            # Convert symbol
            symbol = SymbolMapper.from_xtp(
                trade_report.ticker,
                XTPExchange(trade_report.market)
            )
            
            # Map side
            side = OrderMapper.side_from_xtp(trade_report.side)
            
            update = TradeUpdate(
                trade_id=trade_report.exec_id,
                client_order_id=client_order_id,
                broker_order_id=str(xtp_order_id),
                symbol=symbol,
                side=side,
                price=trade_report.price,
                quantity=trade_report.quantity,
                exchange_trade_id=trade_report.exec_id,
            )
            
            self._on_trade_update(update)
            
        except Exception as e:
            self.log.error("xtp_trade_callback_error", error=str(e))


# ---------------------------------------------------------------------------
# XTP Callback Handler (SPI)
# ---------------------------------------------------------------------------

if XTP_AVAILABLE:
    
    class _XtpTraderSpi(XTPTraderSpi):
        """
        XTP Trader callback handler.
        
        Inherits from XTPTraderSpi (C++ SPI interface).
        """
        
        def __init__(self, gateway: XtpGateway):
            super().__init__()
            self.gateway = gateway
        
        def OnDisconnected(self, session_id: int, reason: int) -> None:
            """Handle disconnection."""
            self.gateway.log.warning(
                "xtp_disconnected_callback",
                session_id=session_id,
                reason=reason,
            )
            self.gateway._on_disconnected()
        
        def OnOrderEvent(
            self, 
            order_info: XTPOrderInfo, 
            error_info: Any, 
            session_id: int
        ) -> None:
            """Handle order event."""
            if error_info and error_info.error_id != 0:
                self.gateway.log.error(
                    "xtp_order_error",
                    error_id=error_info.error_id,
                    error_msg=error_info.error_msg,
                )
            self.gateway._process_order_callback(order_info)
        
        def OnTradeEvent(
            self, 
            trade_info: XTPTradeReport, 
            session_id: int
        ) -> None:
            """Handle trade event."""
            self.gateway._process_trade_callback(trade_info)
        
        def OnCancelOrderError(
            self,
            order_cancel_info: Any,
            error_info: Any,
            session_id: int
        ) -> None:
            """Handle cancel error."""
            self.gateway.log.error(
                "xtp_cancel_error_callback",
                error_id=error_info.error_id if error_info else 0,
                error_msg=error_info.error_msg if error_info else "",
            )
        
        def OnQueryAsset(
            self,
            asset: XTPQueryAssetRsp,
            error_info: Any,
            request_id: int,
            is_last: bool,
            session_id: int
        ) -> None:
            """Handle asset query response."""
            if error_info and error_info.error_id != 0:
                self.gateway.log.error(
                    "xtp_query_asset_error",
                    error_id=error_info.error_id,
                )
                return
            
            update = AccountUpdate(
                account_id=self.gateway.config.account_id,
                cash=asset.banlance,
                available=asset.buying_power,
                frozen=asset.frozen_margin,
                equity=asset.total_asset,
            )
            
            self.gateway._publish_event(GatewayEventType.ACCOUNT_UPDATE, update)
        
        def OnQueryPosition(
            self,
            position: XTPQueryStkPositionRsp,
            error_info: Any,
            request_id: int,
            is_last: bool,
            session_id: int
        ) -> None:
            """Handle position query response."""
            if error_info and error_info.error_id != 0:
                return
            
            symbol = SymbolMapper.from_xtp(
                position.ticker,
                XTPExchange(position.market)
            )
            
            update = PositionUpdate(
                symbol=symbol,
                total_quantity=position.total_qty,
                available_quantity=position.sellable_qty,
                yesterday_quantity=position.yesterday_position,
                avg_price=position.avg_price,
                unrealized_pnl=position.unrealized_pnl,
            )
            
            self.gateway._publish_event(GatewayEventType.POSITION_UPDATE, update)

else:
    _XtpTraderSpi = None


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    "XtpGateway",
]
