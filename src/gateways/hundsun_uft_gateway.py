"""
Hundsun UFT Gateway - 恒生UFT极速交易网关

Implements live trading connection via Hundsun UFT (恒生极速交易接口).
This is the standard institutional trading interface.

V3.2.0: Initial release

Features:
- Standard institutional trading interface
- Request/Response/Callback (ReqXXX/OnRspXXX/OnRtnXXX) pattern
- Support for SSE, SZSE, BSE markets
- Order submission (limit, market, FAK, FOK)
- Order cancellation
- Real-time order/trade callbacks
- Auto-reconnection with state recovery

Architecture:
    HundsunUftGateway
    ├── CHSTradeApi - Trading API
    ├── CHSTradeSpi - Trading callbacks
    └── CHSMdApi (optional) - Market data API

Dependencies:
- Hundsun UFT SDK (C++ SDK with Python bindings)
- Trading account from broker using Hundsun system

Usage:
    >>> from src.gateways import HundsunUftGateway, GatewayConfig
    >>> from queue import Queue
    >>> 
    >>> config = GatewayConfig(
    ...     account_id="YOUR_ACCOUNT",
    ...     broker="hundsun",
    ...     password="YOUR_PASSWORD",  # Or use env: UFT_PASSWORD
    ...     td_front="tcp://x.x.x.x:port",
    ...     md_front="tcp://x.x.x.x:port",
    ... )
    >>> 
    >>> event_queue = Queue()
    >>> gateway = HundsunUftGateway(config, event_queue)
    >>> 
    >>> # Connect and login
    >>> gateway.connect()
    >>> 
    >>> # Send order
    >>> order_id = gateway.send_order(
    ...     symbol="600519.SH",
    ...     side="buy",
    ...     quantity=100,
    ...     price=1800.0,
    ... )

API Pattern:
    Request:  ReqOrderInsert(pInputOrder, nRequestID)
    Response: OnRspOrderInsert(pInputOrder, pRspInfo, nRequestID, bIsLast)
    Report:   OnRtnOrder(pOrder)
              OnRtnTrade(pTrade)

References:
- Hundsun Official Docs: https://www.hs.net/home/openapi/
- vn.py UFT Implementation: https://www.vnpy.com/forum/topic/31782
"""
from __future__ import annotations

import os
import threading
import time
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
from src.gateways.mappers import SymbolMapper, OrderMapper, UFTExchange


# Check if Hundsun SDK is available
UFT_AVAILABLE = False
hsuft_api = None

try:
    # The actual import depends on how UFT SDK is packaged
    # Common names: hsuft, chsapi, etc.
    import hsuft_api  # type: ignore
    from hsuft_api import (  # type: ignore
        CHSTradeApi,
        CHSTradeSpi,
        CHSMdApi,
        CHSMdSpi,
    )
    UFT_AVAILABLE = True
except ImportError:
    pass  # Use stub mode


# ---------------------------------------------------------------------------
# UFT Data Structures (Stub definitions matching UFT API)
# ---------------------------------------------------------------------------

class CHSInputOrderField:
    """Input order structure for ReqOrderInsert."""
    exchange_id: str = ""       # 交易所代码
    stock_code: str = ""        # 证券代码
    entrust_direction: str = "" # 委托方向 1=买 2=卖
    price_type: str = ""        # 价格类型 0=限价 1=市价
    entrust_price: float = 0.0  # 委托价格
    entrust_amount: int = 0     # 委托数量
    order_ref: str = ""         # 报单引用（客户端订单号）


class CHSOrderField:
    """Order information from OnRtnOrder."""
    entrust_no: str = ""        # 委托编号（柜台订单号）
    order_ref: str = ""         # 报单引用
    exchange_id: str = ""       # 交易所代码
    stock_code: str = ""        # 证券代码
    entrust_direction: str = "" # 委托方向
    price_type: str = ""        # 价格类型
    entrust_price: float = 0.0  # 委托价格
    entrust_amount: int = 0     # 委托数量
    business_amount: int = 0    # 成交数量
    business_price: float = 0.0 # 成交价格
    entrust_status: str = ""    # 委托状态
    cancel_info: str = ""       # 撤单原因/废单原因


class CHSTradeField:
    """Trade information from OnRtnTrade."""
    business_no: str = ""       # 成交编号
    entrust_no: str = ""        # 委托编号
    order_ref: str = ""         # 报单引用
    exchange_id: str = ""       # 交易所代码
    stock_code: str = ""        # 证券代码
    entrust_direction: str = "" # 委托方向
    business_price: float = 0.0 # 成交价格
    business_amount: int = 0    # 成交数量
    business_time: str = ""     # 成交时间
    business_balance: float = 0.0  # 成交金额


class CHSFundField:
    """Fund (account) information."""
    current_balance: float = 0.0    # 当前余额
    enable_balance: float = 0.0     # 可用余额
    frozen_balance: float = 0.0     # 冻结金额
    market_value: float = 0.0       # 证券市值
    asset_balance: float = 0.0      # 总资产


class CHSPositionField:
    """Position information."""
    exchange_id: str = ""       # 交易所代码
    stock_code: str = ""        # 证券代码
    stock_name: str = ""        # 证券名称
    current_amount: int = 0     # 当前数量
    enable_amount: int = 0      # 可用数量
    frozen_amount: int = 0      # 冻结数量
    cost_price: float = 0.0     # 成本价
    last_price: float = 0.0     # 最新价
    market_value: float = 0.0   # 市值
    profit_loss: float = 0.0    # 盈亏


class CHSRspInfoField:
    """Response info structure."""
    error_id: int = 0
    error_msg: str = ""


# ---------------------------------------------------------------------------
# Hundsun UFT Gateway Implementation
# ---------------------------------------------------------------------------

class HundsunUftGateway(BaseLiveGateway):
    """
    恒生UFT极速交易网关
    
    通过恒生UFT SDK连接极速交易柜台进行实盘交易。
    
    Connection Flow:
    1. Create CHSTradeApi instance
    2. Register CHSTradeSpi callback handler
    3. Connect to front server
    4. User login
    5. Subscribe to events
    6. Trading ready
    
    API Pattern (类CTP模式):
    - ReqXXX: 发送请求
    - OnRspXXX: 请求响应
    - OnRtnXXX: 数据推送（委托回报、成交回报等）
    
    Thread Model:
    - UFT uses internal threads for network I/O
    - Callbacks are invoked on UFT's thread
    - Gateway normalizes and forwards to event queue
    
    Order ID Mapping:
    - client_order_id: Generated by gateway (UFT-00000001)
    - broker_order_id: entrust_no from UFT (委托编号)
    - order_ref: 报单引用 (maps to client_order_id)
    """
    
    def __init__(
        self,
        config: GatewayConfig,
        event_queue: Queue,
        logger=None,
    ):
        """
        Initialize Hundsun UFT gateway.
        
        Args:
            config: Gateway configuration
            event_queue: Queue for event publishing
            logger: Optional logger instance
        """
        super().__init__(config, event_queue, logger)
        
        # Stub mode if SDK not available
        self._stub_mode = not UFT_AVAILABLE
        
        if self._stub_mode:
            self.log.warning(
                "uft_gateway_stub_mode",
                msg="Hundsun UFT SDK not available, running in stub mode"
            )
        
        # API instances
        self._trade_api = None
        self._trade_spi = None
        self._md_api = None
        self._md_spi = None
        
        # Session state
        self._front_id = 0
        self._session_id = 0
        self._order_ref = 0
        self._order_ref_lock = threading.Lock()
        
        # Request tracking
        self._request_id = 0
        self._request_lock = threading.Lock()
        self._pending_requests: Dict[int, str] = {}  # request_id -> request_type
        
        # Order ref to entrust_no mapping
        self._order_ref_to_entrust: Dict[str, str] = {}
        self._entrust_to_order_ref: Dict[str, str] = {}
        
        # Login status
        self._login_status = False
        
        # Log path
        self._log_path = Path("./logs/uft")
        self._log_path.mkdir(parents=True, exist_ok=True)
        
        self.log.info(
            "uft_gateway_initialized",
            account_id=config.account_id,
            td_front=config.td_front,
            stub_mode=self._stub_mode,
        )
    
    def _next_order_ref(self) -> str:
        """Generate next order reference."""
        with self._order_ref_lock:
            self._order_ref += 1
            return f"{self._front_id:04d}{self._session_id:04d}{self._order_ref:08d}"
    
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
        Connect to Hundsun UFT server.
        
        Returns:
            True if connection successful
        """
        if self._stub_mode:
            return self._stub_connect()
        
        try:
            # Create TradeApi
            self._trade_api = CHSTradeApi.CreateApi(str(self._log_path))
            
            # Create and register callback handler
            self._trade_spi = _HundsunTradeSpi(self)
            self._trade_api.RegisterSpi(self._trade_spi)
            
            # Subscribe to events (all topics)
            self._trade_api.SubscribePrivateTopic(0)  # RESTART mode
            self._trade_api.SubscribePublicTopic(0)
            
            # Register front address
            td_front = self.config.td_front or ""
            self._trade_api.RegisterFront(td_front)
            
            # Init (triggers OnFrontConnected callback)
            self._trade_api.Init()
            
            # Wait for connection (with timeout)
            timeout = 10.0
            start = time.time()
            while not self._connected and time.time() - start < timeout:
                time.sleep(0.1)
            
            if self._connected:
                # Perform login
                return self._do_login()
            else:
                self.log.error("uft_connect_timeout")
                return False
                
        except Exception as e:
            self.log.error("uft_connect_error", error=str(e))
            return False
    
    def _do_login(self) -> bool:
        """
        Perform user login after connection.
        
        Returns:
            True if login successful
        """
        if self._stub_mode:
            return True
        
        try:
            # Build login request
            login_req = {
                "fund_account": self.config.account_id,
                "password": self.config.password or os.environ.get("UFT_PASSWORD", ""),
            }
            
            request_id = self._next_request_id()
            self._pending_requests[request_id] = "login"
            
            # Send login request
            result = self._trade_api.ReqUserLogin(login_req, request_id)
            
            if result != 0:
                self.log.error("uft_login_request_failed", result=result)
                return False
            
            # Wait for login response
            timeout = 10.0
            start = time.time()
            while not self._login_status and time.time() - start < timeout:
                time.sleep(0.1)
            
            return self._login_status
            
        except Exception as e:
            self.log.error("uft_login_error", error=str(e))
            return False
    
    def _stub_connect(self) -> bool:
        """Stub connection for development."""
        self._front_id = 1
        self._session_id = 1
        self._login_status = True
        self.log.info("uft_stub_connected", account=self.config.account_id)
        return True
    
    def _do_disconnect(self) -> None:
        """Disconnect from UFT server."""
        if self._stub_mode:
            self._login_status = False
            self.log.info("uft_stub_disconnected")
            return
        
        try:
            if self._trade_api:
                # Logout first
                if self._login_status:
                    logout_req = {}
                    self._trade_api.ReqUserLogout(logout_req, self._next_request_id())
                
                # Release API
                self._trade_api.Release()
            
            self._trade_api = None
            self._trade_spi = None
            self._login_status = False
            
            self.log.info("uft_disconnected")
            
        except Exception as e:
            self.log.error("uft_disconnect_error", error=str(e))
    
    def _on_front_connected(self) -> None:
        """Handle front connection event from SPI."""
        self._connected = True
        self.log.info("uft_front_connected")
    
    def _on_front_disconnected(self, reason: int) -> None:
        """Handle front disconnection event from SPI."""
        self._connected = False
        self._login_status = False
        self.log.warning("uft_front_disconnected", reason=reason)
        self._on_disconnected()
    
    def _on_rsp_user_login(
        self, 
        rsp_user_login: Any, 
        rsp_info: CHSRspInfoField, 
        request_id: int
    ) -> None:
        """Handle login response from SPI."""
        if rsp_info and rsp_info.error_id != 0:
            self.log.error(
                "uft_login_failed",
                error_id=rsp_info.error_id,
                error_msg=rsp_info.error_msg,
            )
            self._login_status = False
            return
        
        # Extract session info
        self._front_id = getattr(rsp_user_login, 'front_id', 1)
        self._session_id = getattr(rsp_user_login, 'session_id', 1)
        self._login_status = True
        
        self.log.info(
            "uft_login_success",
            front_id=self._front_id,
            session_id=self._session_id,
        )
    
    def _do_heartbeat(self) -> None:
        """UFT handles heartbeat internally."""
        pass
    
    # ---------------------------------------------------------------------------
    # Order Management
    # ---------------------------------------------------------------------------
    
    def _do_send_order(self, request: OrderRequest) -> str:
        """
        Send order via UFT ReqOrderInsert.
        
        Args:
            request: Order request
            
        Returns:
            order_ref (client order reference)
        """
        if self._stub_mode:
            return self._stub_send_order(request)
        
        if not self._trade_api or not self._login_status:
            raise RuntimeError("UFT not connected or not logged in")
        
        # Generate order reference
        order_ref = self._next_order_ref()
        
        # Convert symbol to UFT format
        code, exchange_id = SymbolMapper.to_uft(request.symbol)
        
        # Build order insert request
        input_order = CHSInputOrderField()
        input_order.exchange_id = exchange_id
        input_order.stock_code = code
        input_order.entrust_direction = OrderMapper.side_to_uft(request.side)
        input_order.price_type = OrderMapper.order_type_to_uft(request.order_type)
        input_order.entrust_price = request.price or 0.0
        input_order.entrust_amount = int(request.quantity)
        input_order.order_ref = order_ref
        
        # Map order_ref to client_order_id
        self._order_ref_to_entrust[order_ref] = ""  # Will be filled by OnRtnOrder
        self._client_to_broker[request.client_order_id] = order_ref
        self._broker_to_client[order_ref] = request.client_order_id
        
        try:
            # Send order
            result = self._trade_api.ReqOrderInsert(
                input_order.__dict__,
                self._next_request_id()
            )
            
            if result != 0:
                raise RuntimeError(f"ReqOrderInsert failed: {result}")
            
            self.log.info(
                "uft_order_sent",
                client_order_id=request.client_order_id,
                order_ref=order_ref,
                symbol=request.symbol,
            )
            
            # Return order_ref as broker_order_id initially
            # Real entrust_no will come from OnRtnOrder
            return order_ref
            
        except Exception as e:
            self._broker_to_client.pop(order_ref, None)
            self._client_to_broker.pop(request.client_order_id, None)
            raise RuntimeError(f"Order submission failed: {e}")
    
    def _stub_send_order(self, request: OrderRequest) -> str:
        """Stub order for development."""
        order_ref = self._next_order_ref()
        entrust_no = f"STUB-{int(time.time() * 1000) % 1000000}"
        
        self._order_ref_to_entrust[order_ref] = entrust_no
        self._entrust_to_order_ref[entrust_no] = order_ref
        self._client_to_broker[request.client_order_id] = entrust_no
        self._broker_to_client[entrust_no] = request.client_order_id
        
        self.log.info(
            "uft_stub_order_sent",
            client_order_id=request.client_order_id,
            order_ref=order_ref,
            entrust_no=entrust_no,
        )
        
        # Simulate order accepted
        self._simulate_order_accepted(request, order_ref, entrust_no)
        
        return entrust_no
    
    def _simulate_order_accepted(
        self, 
        request: OrderRequest, 
        order_ref: str,
        entrust_no: str
    ) -> None:
        """Simulate order acceptance for stub mode."""
        update = OrderUpdate(
            client_order_id=request.client_order_id,
            broker_order_id=entrust_no,
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
        Cancel order via UFT ReqOrderAction.
        
        Args:
            broker_order_id: entrust_no or order_ref
            client_order_id: Client order ID
            
        Returns:
            True if cancel request sent
        """
        if self._stub_mode:
            return self._stub_cancel_order(broker_order_id, client_order_id)
        
        if not self._trade_api or not self._login_status:
            raise RuntimeError("UFT not connected or not logged in")
        
        # Get order info
        order = self._orders.get(client_order_id)
        if not order:
            raise ValueError(f"Order not found: {client_order_id}")
        
        # Get entrust_no
        entrust_no = broker_order_id
        if broker_order_id in self._order_ref_to_entrust:
            entrust_no = self._order_ref_to_entrust[broker_order_id]
        
        # Build cancel request
        code, exchange_id = SymbolMapper.to_uft(order.symbol)
        
        order_action = {
            "exchange_id": exchange_id,
            "stock_code": code,
            "entrust_no": entrust_no,
        }
        
        try:
            result = self._trade_api.ReqOrderAction(
                order_action,
                self._next_request_id()
            )
            
            if result != 0:
                self.log.error("uft_cancel_failed", result=result)
                return False
            
            self.log.info(
                "uft_cancel_sent",
                client_order_id=client_order_id,
                entrust_no=entrust_no,
            )
            
            return True
            
        except Exception as e:
            self.log.error("uft_cancel_error", error=str(e))
            raise
    
    def _stub_cancel_order(
        self, 
        broker_order_id: str, 
        client_order_id: str
    ) -> bool:
        """Stub cancel for development."""
        self.log.info(
            "uft_stub_cancel_sent",
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
        """Query account from UFT."""
        if self._stub_mode:
            return self._stub_query_account()
        
        if not self._trade_api or not self._login_status:
            return None
        
        try:
            # Query fund
            query_req = {}
            request_id = self._next_request_id()
            self._pending_requests[request_id] = "query_fund"
            
            result = self._trade_api.ReqQryFund(query_req, request_id)
            
            if result != 0:
                self.log.error("uft_query_fund_failed", result=result)
                return None
            
            # Response comes via OnRspQryFund callback
            return None
            
        except Exception as e:
            self.log.error("uft_query_account_error", error=str(e))
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
        """Query positions from UFT."""
        if self._stub_mode:
            return self._stub_query_positions()
        
        if not self._trade_api or not self._login_status:
            return []
        
        try:
            query_req = {}
            request_id = self._next_request_id()
            self._pending_requests[request_id] = "query_position"
            
            result = self._trade_api.ReqQryPosition(query_req, request_id)
            
            if result != 0:
                self.log.error("uft_query_position_failed", result=result)
                return []
            
            # Response comes via OnRspQryPosition callback
            return []
            
        except Exception as e:
            self.log.error("uft_query_positions_error", error=str(e))
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
        """Query open orders from UFT."""
        if self._stub_mode:
            return []
        
        if not self._trade_api or not self._login_status:
            return []
        
        try:
            query_req = {}
            request_id = self._next_request_id()
            self._pending_requests[request_id] = "query_order"
            
            result = self._trade_api.ReqQryOrder(query_req, request_id)
            
            if result != 0:
                self.log.error("uft_query_order_failed", result=result)
            
            return []
            
        except Exception as e:
            self.log.error("uft_query_orders_error", error=str(e))
            return []
    
    # ---------------------------------------------------------------------------
    # Callback Processing (called by SPI)
    # ---------------------------------------------------------------------------
    
    def _on_rtn_order(self, order_field: CHSOrderField) -> None:
        """Process order callback from UFT OnRtnOrder."""
        try:
            entrust_no = order_field.entrust_no
            order_ref = order_field.order_ref
            
            # Update order_ref to entrust_no mapping
            if order_ref and order_ref in self._order_ref_to_entrust:
                self._order_ref_to_entrust[order_ref] = entrust_no
                self._entrust_to_order_ref[entrust_no] = order_ref
            
            # Find client order ID
            client_order_id = self._broker_to_client.get(order_ref, "")
            if not client_order_id:
                client_order_id = self._broker_to_client.get(entrust_no, "")
            if not client_order_id:
                client_order_id = f"UFT-{entrust_no}"
            
            # Convert symbol
            symbol = SymbolMapper.from_uft(
                order_field.stock_code,
                order_field.exchange_id
            )
            
            # Map status and side
            status = OrderMapper.status_from_uft(order_field.entrust_status)
            side = OrderMapper.side_from_uft(order_field.entrust_direction)
            
            update = OrderUpdate(
                client_order_id=client_order_id,
                broker_order_id=entrust_no,
                symbol=symbol,
                side=side,
                status=status,
                order_type=OrderMapper.order_type_from_uft(order_field.price_type),
                price=order_field.entrust_price,
                quantity=order_field.entrust_amount,
                filled_quantity=order_field.business_amount,
                avg_fill_price=order_field.business_price,
                error_msg=order_field.cancel_info,
            )
            
            # Update broker ID mapping if needed
            if client_order_id and entrust_no:
                self._client_to_broker[client_order_id] = entrust_no
                self._broker_to_client[entrust_no] = client_order_id
            
            self._on_order_update(update)
            
        except Exception as e:
            self.log.error("uft_order_callback_error", error=str(e))
    
    def _on_rtn_trade(self, trade_field: CHSTradeField) -> None:
        """Process trade callback from UFT OnRtnTrade."""
        try:
            trade_id = trade_field.business_no
            entrust_no = trade_field.entrust_no
            order_ref = trade_field.order_ref
            
            # Find client order ID
            client_order_id = self._broker_to_client.get(order_ref, "")
            if not client_order_id:
                client_order_id = self._broker_to_client.get(entrust_no, "")
            
            # Convert symbol
            symbol = SymbolMapper.from_uft(
                trade_field.stock_code,
                trade_field.exchange_id
            )
            
            # Map side
            side = OrderMapper.side_from_uft(trade_field.entrust_direction)
            
            update = TradeUpdate(
                trade_id=trade_id,
                client_order_id=client_order_id,
                broker_order_id=entrust_no,
                symbol=symbol,
                side=side,
                price=trade_field.business_price,
                quantity=trade_field.business_amount,
                exchange_trade_id=trade_id,
            )
            
            self._on_trade_update(update)
            
        except Exception as e:
            self.log.error("uft_trade_callback_error", error=str(e))
    
    def _on_rsp_qry_fund(self, fund_field: CHSFundField) -> None:
        """Process fund query response."""
        try:
            update = AccountUpdate(
                account_id=self.config.account_id,
                cash=fund_field.current_balance,
                available=fund_field.enable_balance,
                frozen=fund_field.frozen_balance,
                equity=fund_field.asset_balance,
            )
            
            self._publish_event(GatewayEventType.ACCOUNT_UPDATE, update)
            
        except Exception as e:
            self.log.error("uft_fund_callback_error", error=str(e))
    
    def _on_rsp_qry_position(self, position_field: CHSPositionField) -> None:
        """Process position query response."""
        try:
            symbol = SymbolMapper.from_uft(
                position_field.stock_code,
                position_field.exchange_id
            )
            
            update = PositionUpdate(
                symbol=symbol,
                total_quantity=position_field.current_amount,
                available_quantity=position_field.enable_amount,
                frozen_quantity=position_field.frozen_amount,
                avg_price=position_field.cost_price,
                market_value=position_field.market_value,
                unrealized_pnl=position_field.profit_loss,
                last_price=position_field.last_price,
            )
            
            self._publish_event(GatewayEventType.POSITION_UPDATE, update)
            
        except Exception as e:
            self.log.error("uft_position_callback_error", error=str(e))


# ---------------------------------------------------------------------------
# UFT Callback Handler (SPI)
# ---------------------------------------------------------------------------

if UFT_AVAILABLE:
    
    class _HundsunTradeSpi(CHSTradeSpi):
        """
        Hundsun UFT Trade callback handler.
        
        Inherits from CHSTradeSpi (C++ SPI interface).
        Delegates all callbacks to HundsunUftGateway methods.
        """
        
        def __init__(self, gateway: HundsunUftGateway):
            super().__init__()
            self.gateway = gateway
        
        def OnFrontConnected(self) -> None:
            """Front connected callback."""
            self.gateway._on_front_connected()
        
        def OnFrontDisconnected(self, reason: int) -> None:
            """Front disconnected callback."""
            self.gateway._on_front_disconnected(reason)
        
        def OnRspUserLogin(
            self,
            pRspUserLogin: Any,
            pRspInfo: CHSRspInfoField,
            nRequestID: int,
            bIsLast: bool
        ) -> None:
            """Login response callback."""
            self.gateway._on_rsp_user_login(pRspUserLogin, pRspInfo, nRequestID)
        
        def OnRspOrderInsert(
            self,
            pInputOrder: Any,
            pRspInfo: CHSRspInfoField,
            nRequestID: int,
            bIsLast: bool
        ) -> None:
            """Order insert response callback."""
            if pRspInfo and pRspInfo.error_id != 0:
                self.gateway.log.error(
                    "uft_order_insert_error",
                    error_id=pRspInfo.error_id,
                    error_msg=pRspInfo.error_msg,
                )
        
        def OnRspOrderAction(
            self,
            pInputOrderAction: Any,
            pRspInfo: CHSRspInfoField,
            nRequestID: int,
            bIsLast: bool
        ) -> None:
            """Order action (cancel) response callback."""
            if pRspInfo and pRspInfo.error_id != 0:
                self.gateway.log.error(
                    "uft_order_action_error",
                    error_id=pRspInfo.error_id,
                    error_msg=pRspInfo.error_msg,
                )
        
        def OnRtnOrder(self, pOrder: CHSOrderField) -> None:
            """Order report callback."""
            self.gateway._on_rtn_order(pOrder)
        
        def OnRtnTrade(self, pTrade: CHSTradeField) -> None:
            """Trade report callback."""
            self.gateway._on_rtn_trade(pTrade)
        
        def OnRspQryFund(
            self,
            pFund: CHSFundField,
            pRspInfo: CHSRspInfoField,
            nRequestID: int,
            bIsLast: bool
        ) -> None:
            """Fund query response callback."""
            if pRspInfo and pRspInfo.error_id != 0:
                self.gateway.log.error(
                    "uft_qry_fund_error",
                    error_id=pRspInfo.error_id,
                )
                return
            
            if pFund:
                self.gateway._on_rsp_qry_fund(pFund)
        
        def OnRspQryPosition(
            self,
            pPosition: CHSPositionField,
            pRspInfo: CHSRspInfoField,
            nRequestID: int,
            bIsLast: bool
        ) -> None:
            """Position query response callback."""
            if pRspInfo and pRspInfo.error_id != 0:
                return
            
            if pPosition:
                self.gateway._on_rsp_qry_position(pPosition)
        
        def OnRspError(
            self,
            pRspInfo: CHSRspInfoField,
            nRequestID: int,
            bIsLast: bool
        ) -> None:
            """Error response callback."""
            self.gateway.log.error(
                "uft_error_callback",
                error_id=pRspInfo.error_id if pRspInfo else 0,
                error_msg=pRspInfo.error_msg if pRspInfo else "",
                request_id=nRequestID,
            )

else:
    _HundsunTradeSpi = None


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    "HundsunUftGateway",
]
