"""
Base Live Gateway - 实盘交易网关抽象基类

Provides abstract base class and common utilities for live trading gateways.
All concrete gateway implementations (XtQuant, XTP, Hundsun UFT) inherit from this.

V3.2.0: Initial release

Features:
- Unified interface for all broker connections
- Thread-safe event publishing
- Automatic reconnection handling
- Order state machine management
- Rate limiting support

Architecture:
    BaseLiveGateway (Abstract)
    ├── XtQuantGateway - QMT/MiniQMT implementation
    ├── XtpGateway - 中泰XTP implementation
    └── HundsunUftGateway - 恒生UFT implementation

Usage:
    >>> class MyGateway(BaseLiveGateway):
    ...     def _do_connect(self) -> bool:
    ...         # Implement broker-specific connection
    ...         return True
    ...     
    ...     def _do_send_order(self, request: OrderRequest) -> str:
    ...         # Implement broker-specific order submission
    ...         return broker_order_id
"""
from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from queue import Queue
from typing import Any, Callable, Dict, List, Optional, Set

from src.core.logger import get_logger


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class GatewayStatus(str, Enum):
    """Gateway connection status."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATED = "authenticated"
    RECONNECTING = "reconnecting"
    ERROR = "error"
    CLOSED = "closed"


class OrderStatus(str, Enum):
    """
    Unified order status for internal state machine.
    
    State transitions:
        PENDING_SUBMIT -> SUBMITTED -> PARTIALLY_FILLED -> FILLED
                       -> CANCEL_PENDING -> CANCELLED
                       -> REJECTED
                       -> ERROR
    """
    PENDING_SUBMIT = "pending_submit"  # Created locally, not yet sent
    SUBMITTED = "submitted"            # Accepted by broker
    PARTIALLY_FILLED = "partial_fill"  # Partially executed
    FILLED = "filled"                  # Fully executed
    CANCEL_PENDING = "cancel_pending"  # Cancel request sent
    CANCELLED = "cancelled"            # Successfully cancelled
    REJECTED = "rejected"              # Rejected by broker/exchange
    EXPIRED = "expired"                # Order expired
    ERROR = "error"                    # Error state


class OrderType(str, Enum):
    """Order type enumeration."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    FAK = "fak"  # Fill and Kill
    FOK = "fok"  # Fill or Kill


class OrderSide(str, Enum):
    """Order side enumeration."""
    BUY = "buy"
    SELL = "sell"


class TimeInForce(str, Enum):
    """Time in force for orders."""
    GTC = "gtc"  # Good Till Cancel
    DAY = "day"  # Day order
    IOC = "ioc"  # Immediate or Cancel
    FOK = "fok"  # Fill or Kill


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class GatewayConfig:
    """
    Gateway configuration container.
    
    Attributes:
        account_id: Trading account identifier
        broker: Broker type (xtquant, xtp, hundsun, etc.)
        password: Account password (prefer env variable)
        
    Broker-specific fields:
        terminal_path: Path to QMT/MiniQMT terminal
        trade_server: Trading server address
        quote_server: Quote server address
        client_id: Client identifier
    """
    account_id: str
    broker: str = "xtquant"
    
    # Authentication (prefer environment variables)
    password: Optional[str] = None
    
    # XtQuant/QMT specific
    terminal_type: str = "QMT"  # QMT or MiniQMT
    terminal_path: Optional[str] = None
    
    # XTP specific
    trade_server: Optional[str] = None
    quote_server: Optional[str] = None
    client_id: int = 1
    
    # Hundsun UFT specific
    td_front: Optional[str] = None
    md_front: Optional[str] = None
    
    # Common settings
    auto_reconnect: bool = True
    reconnect_interval: float = 5.0  # seconds
    max_reconnect_attempts: int = 10
    heartbeat_interval: float = 30.0  # seconds
    
    # Rate limiting
    max_orders_per_second: float = 10.0

    # SDK path configuration (XTP/UFT custom SDK location)
    sdk_path: Optional[str] = None
    sdk_log_path: Optional[str] = None

    def __post_init__(self):
        """Validate configuration."""
        if not self.account_id:
            raise ValueError("account_id is required")
        if self.sdk_path:
            import sys
            from pathlib import Path
            resolved = str(Path(self.sdk_path).resolve())
            if resolved not in sys.path:
                sys.path.insert(0, resolved)


@dataclass
class OrderRequest:
    """
    Order request for sending to broker.
    
    Internal representation before sending to broker API.
    """
    symbol: str
    side: OrderSide
    quantity: float
    price: Optional[float] = None
    order_type: OrderType = OrderType.LIMIT
    time_in_force: TimeInForce = TimeInForce.DAY
    
    # Internal tracking
    client_order_id: str = ""
    strategy_id: str = ""
    
    # Risk parameters
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    # Metadata
    create_time: datetime = field(default_factory=datetime.now)
    tags: Dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate order request."""
        if self.quantity <= 0:
            raise ValueError(f"Quantity must be positive: {self.quantity}")
        if self.order_type == OrderType.LIMIT and self.price is None:
            raise ValueError("Limit order requires price")


@dataclass
class OrderUpdate:
    """
    Order status update from broker.
    
    Represents order state changes received from broker callbacks.
    """
    client_order_id: str
    broker_order_id: str
    symbol: str
    side: OrderSide
    status: OrderStatus
    
    # Order details
    order_type: OrderType = OrderType.LIMIT
    price: float = 0.0
    quantity: float = 0.0
    filled_quantity: float = 0.0
    avg_fill_price: float = 0.0
    
    # Timestamps
    create_time: Optional[datetime] = None
    update_time: datetime = field(default_factory=datetime.now)
    
    # Error information
    error_code: str = ""
    error_msg: str = ""
    
    # Exchange order info
    exchange_order_id: str = ""


@dataclass
class TradeUpdate:
    """
    Trade execution update from broker.
    
    Represents individual trade (fill) received from broker.
    """
    trade_id: str
    client_order_id: str
    broker_order_id: str
    symbol: str
    side: OrderSide
    
    # Execution details
    price: float
    quantity: float
    commission: float = 0.0
    
    # Timestamps
    trade_time: datetime = field(default_factory=datetime.now)
    
    # Exchange trade info
    exchange_trade_id: str = ""
    
    @property
    def value(self) -> float:
        """Trade value (price * quantity)."""
        return self.price * self.quantity
    
    @property
    def net_value(self) -> float:
        """Net value after commission."""
        return self.value - self.commission


@dataclass
class AccountUpdate:
    """
    Account information update.
    
    Contains cash, margin, and equity information.
    """
    account_id: str
    cash: float = 0.0
    available: float = 0.0
    frozen: float = 0.0
    margin: float = 0.0
    equity: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    
    update_time: datetime = field(default_factory=datetime.now)
    
    @property
    def buying_power(self) -> float:
        """Available buying power."""
        return self.available


@dataclass
class PositionUpdate:
    """
    Position information update.
    
    Contains position size, cost, and P&L information.
    """
    symbol: str
    
    # Position size
    total_quantity: float = 0.0       # 总持仓
    available_quantity: float = 0.0   # 可用数量
    frozen_quantity: float = 0.0      # 冻结数量
    yesterday_quantity: float = 0.0   # 昨仓
    today_quantity: float = 0.0       # 今仓
    
    # Cost and P&L
    avg_price: float = 0.0
    cost: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    
    # Current price
    last_price: float = 0.0
    
    update_time: datetime = field(default_factory=datetime.now)
    
    @property
    def pnl_pct(self) -> float:
        """P&L percentage."""
        if self.cost == 0:
            return 0.0
        return (self.unrealized_pnl / self.cost) * 100


# ---------------------------------------------------------------------------
# Event Types for Gateway
# ---------------------------------------------------------------------------

class GatewayEventType:
    """Gateway-specific event types."""
    
    # Connection events
    CONNECTED = "gateway.connected"
    DISCONNECTED = "gateway.disconnected"
    RECONNECTING = "gateway.reconnecting"
    ERROR = "gateway.error"
    
    # Order events
    ORDER_SUBMITTED = "gateway.order.submitted"
    ORDER_ACCEPTED = "gateway.order.accepted"
    ORDER_REJECTED = "gateway.order.rejected"
    ORDER_CANCELLED = "gateway.order.cancelled"
    ORDER_FILLED = "gateway.order.filled"
    ORDER_PARTIAL = "gateway.order.partial"
    ORDER_ERROR = "gateway.order.error"
    
    # Trade events
    TRADE_EXECUTED = "gateway.trade.executed"
    
    # Account/Position events
    ACCOUNT_UPDATE = "gateway.account.update"
    POSITION_UPDATE = "gateway.position.update"
    
    # Market data events
    TICK_DATA = "gateway.tick"
    BAR_DATA = "gateway.bar"
    DEPTH_DATA = "gateway.depth"


# ---------------------------------------------------------------------------
# Async Query Result Cache
# ---------------------------------------------------------------------------


class QueryResultCache:
    """Thread-safe cache for async query results with Event synchronization.

    Gateway subclasses call ``prepare(request_id)`` before issuing an async
    query (e.g. ``QueryAsset``) and ``wait_result(request_id)`` to block until
    the callback fires ``set_result``.
    """

    def __init__(self, timeout: float = 5.0):
        self._results: Dict[str, Any] = {}
        self._events: Dict[str, threading.Event] = {}
        self._lock = threading.Lock()
        self._timeout = timeout

    def prepare(self, request_id: str) -> None:
        with self._lock:
            self._events[request_id] = threading.Event()

    def set_result(self, request_id: str, result: Any) -> None:
        with self._lock:
            self._results[request_id] = result
            ev = self._events.get(request_id)
            if ev:
                ev.set()

    def wait_result(self, request_id: str, timeout: Optional[float] = None) -> Optional[Any]:
        ev = self._events.get(request_id)
        if ev is None:
            return None
        ev.wait(timeout=timeout or self._timeout)
        with self._lock:
            self._events.pop(request_id, None)
            return self._results.pop(request_id, None)


# ---------------------------------------------------------------------------
# Base Live Gateway
# ---------------------------------------------------------------------------

class BaseLiveGateway(ABC):
    """
    Abstract base class for live trading gateways.
    
    Provides common functionality:
    - Connection management with auto-reconnect
    - Order ID generation and mapping
    - Thread-safe event publishing
    - Rate limiting
    - State recovery after reconnection
    
    Subclasses must implement:
    - _do_connect(): Broker-specific connection
    - _do_disconnect(): Broker-specific disconnection
    - _do_send_order(): Broker-specific order submission
    - _do_cancel_order(): Broker-specific order cancellation
    - _do_query_account(): Query account information
    - _do_query_positions(): Query all positions
    - _do_query_orders(): Query open orders
    
    Usage:
        >>> gateway = XtQuantGateway(config, event_queue)
        >>> gateway.connect()
        >>> order_id = gateway.send_order("600519.SH", OrderSide.BUY, 100, price=1800.0)
        >>> gateway.cancel_order(order_id)
    """
    
    def __init__(
        self,
        config: GatewayConfig,
        event_queue: Queue,
        logger=None,
    ):
        """
        Initialize gateway.
        
        Args:
            config: Gateway configuration
            event_queue: Queue for publishing events
            logger: Optional logger instance
        """
        self.config = config
        self.event_queue = event_queue
        self.log = logger or get_logger(f"gateway.{config.broker}")
        
        # Connection state
        self._status = GatewayStatus.DISCONNECTED
        self._connected = False
        self._authenticated = False
        self._reconnect_count = 0
        self._last_heartbeat = datetime.now()
        
        # Order tracking
        self._order_seq = 0
        self._order_seq_lock = threading.Lock()
        
        # Order ID mappings: client_order_id <-> broker_order_id
        self._client_to_broker: Dict[str, str] = {}
        self._broker_to_client: Dict[str, str] = {}
        self._orders: Dict[str, OrderUpdate] = {}  # client_order_id -> OrderUpdate
        
        # Trade deduplication
        self._processed_trades: Set[str] = set()
        
        # Rate limiting
        self._last_order_time = 0.0
        self._order_interval = 1.0 / config.max_orders_per_second
        
        # Background threads
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._reconnect_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Callbacks for custom handling
        self._order_callbacks: List[Callable[[OrderUpdate], None]] = []
        self._trade_callbacks: List[Callable[[TradeUpdate], None]] = []
        
        self.log.info(
            "gateway_initialized",
            broker=config.broker,
            account=config.account_id,
        )
    
    # ---------------------------------------------------------------------------
    # Properties
    # ---------------------------------------------------------------------------
    
    @property
    def status(self) -> GatewayStatus:
        """Current gateway status."""
        return self._status
    
    @property
    def is_connected(self) -> bool:
        """Whether gateway is connected."""
        return self._connected and self._status in (
            GatewayStatus.CONNECTED,
            GatewayStatus.AUTHENTICATED,
        )
    
    @property
    def gateway_name(self) -> str:
        """Gateway identifier."""
        return f"{self.config.broker}_{self.config.account_id}"
    
    # ---------------------------------------------------------------------------
    # Connection Management
    # ---------------------------------------------------------------------------
    
    def connect(self) -> bool:
        """
        Connect to broker.
        
        Returns:
            True if connection successful
        """
        if self.is_connected:
            self.log.warning("gateway_already_connected")
            return True
        
        self._status = GatewayStatus.CONNECTING
        self.log.info("gateway_connecting", broker=self.config.broker)
        
        try:
            success = self._do_connect()
            
            if success:
                self._connected = True
                self._status = GatewayStatus.CONNECTED
                self._reconnect_count = 0
                
                # Start heartbeat thread
                self._start_heartbeat()
                
                # Recover state
                self._recover_state()
                
                # Publish connected event
                self._publish_event(GatewayEventType.CONNECTED, {
                    "gateway": self.gateway_name,
                    "broker": self.config.broker,
                    "account": self.config.account_id,
                })
                
                self.log.info("gateway_connected", broker=self.config.broker)
                return True
            else:
                self._status = GatewayStatus.ERROR
                self.log.error("gateway_connect_failed", broker=self.config.broker)
                return False
                
        except Exception as e:
            self._status = GatewayStatus.ERROR
            self.log.error("gateway_connect_error", broker=self.config.broker, error=str(e))
            self._publish_event(GatewayEventType.ERROR, {
                "gateway": self.gateway_name,
                "error": str(e),
            })
            return False
    
    def disconnect(self) -> None:
        """Disconnect from broker."""
        if not self._connected:
            return
        
        self.log.info("gateway_disconnecting", broker=self.config.broker)
        
        # Stop background threads
        self._stop_event.set()
        
        try:
            self._do_disconnect()
        except Exception as e:
            self.log.error("gateway_disconnect_error", error=str(e))
        finally:
            self._connected = False
            self._authenticated = False
            self._status = GatewayStatus.DISCONNECTED
            
            self._publish_event(GatewayEventType.DISCONNECTED, {
                "gateway": self.gateway_name,
            })
            
            self.log.info("gateway_disconnected", broker=self.config.broker)
    
    def close(self) -> None:
        """Close gateway and release resources."""
        self.disconnect()
        self._status = GatewayStatus.CLOSED
        self.log.info("gateway_closed", broker=self.config.broker)
    
    def _start_heartbeat(self) -> None:
        """Start heartbeat thread for connection monitoring."""
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            return
        
        self._stop_event.clear()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            daemon=True,
            name=f"{self.gateway_name}_heartbeat",
        )
        self._heartbeat_thread.start()
    
    def _heartbeat_loop(self) -> None:
        """Heartbeat loop for connection monitoring."""
        while not self._stop_event.is_set():
            try:
                if self.is_connected:
                    self._last_heartbeat = datetime.now()
                    # Subclasses can override _do_heartbeat for custom logic
                    self._do_heartbeat()
            except Exception as e:
                self.log.warning("heartbeat_error", error=str(e))
            
            self._stop_event.wait(self.config.heartbeat_interval)
    
    def _do_heartbeat(self) -> None:
        """
        Perform heartbeat check (override in subclass if needed).
        
        Default implementation does nothing.
        """
        pass
    
    def _on_disconnected(self) -> None:
        """
        Handle disconnection event (called by broker callbacks).
        
        Triggers auto-reconnect if configured.
        """
        self._connected = False
        self._status = GatewayStatus.DISCONNECTED
        
        self._publish_event(GatewayEventType.DISCONNECTED, {
            "gateway": self.gateway_name,
        })
        
        if self.config.auto_reconnect:
            self._start_reconnect()
    
    def _start_reconnect(self) -> None:
        """Start reconnection in background thread."""
        if self._reconnect_thread and self._reconnect_thread.is_alive():
            return
        
        self._reconnect_thread = threading.Thread(
            target=self._reconnect_loop,
            daemon=True,
            name=f"{self.gateway_name}_reconnect",
        )
        self._reconnect_thread.start()
    
    def _reconnect_loop(self) -> None:
        """Reconnection loop with exponential backoff."""
        while not self._stop_event.is_set():
            if self._reconnect_count >= self.config.max_reconnect_attempts:
                self.log.error(
                    "gateway_max_reconnect_exceeded",
                    attempts=self._reconnect_count,
                )
                self._status = GatewayStatus.ERROR
                return
            
            self._reconnect_count += 1
            self._status = GatewayStatus.RECONNECTING
            
            # Exponential backoff
            wait_time = min(
                self.config.reconnect_interval * (2 ** (self._reconnect_count - 1)),
                60.0,  # Max 60 seconds
            )
            
            self.log.info(
                "gateway_reconnecting",
                attempt=self._reconnect_count,
                wait_seconds=wait_time,
            )
            
            self._publish_event(GatewayEventType.RECONNECTING, {
                "gateway": self.gateway_name,
                "attempt": self._reconnect_count,
            })
            
            self._stop_event.wait(wait_time)
            
            if self._stop_event.is_set():
                return
            
            if self.connect():
                self.log.info("gateway_reconnected", attempts=self._reconnect_count)
                return
    
    def _recover_state(self) -> None:
        """
        Recover state after reconnection.
        
        Queries open orders, positions, and account to sync local state.
        """
        self.log.info("gateway_recovering_state")
        
        try:
            # Query and sync open orders
            orders = self._do_query_orders()
            for order in orders:
                self._orders[order.client_order_id] = order
                if order.broker_order_id:
                    self._client_to_broker[order.client_order_id] = order.broker_order_id
                    self._broker_to_client[order.broker_order_id] = order.client_order_id
            
            # Query and publish account
            account = self._do_query_account()
            if account:
                self._publish_event(GatewayEventType.ACCOUNT_UPDATE, account)
            
            # Query and publish positions
            positions = self._do_query_positions()
            for pos in positions:
                self._publish_event(GatewayEventType.POSITION_UPDATE, pos)
            
            self.log.info(
                "gateway_state_recovered",
                open_orders=len(orders),
                positions=len(positions),
            )
            
        except Exception as e:
            self.log.error("gateway_state_recovery_error", error=str(e))
    
    # ---------------------------------------------------------------------------
    # Order Management
    # ---------------------------------------------------------------------------
    
    def send_order(
        self,
        symbol: str,
        side: OrderSide | str,
        quantity: float,
        price: Optional[float] = None,
        order_type: OrderType | str = OrderType.LIMIT,
        time_in_force: TimeInForce = TimeInForce.DAY,
        strategy_id: str = "",
        **kwargs,
    ) -> str:
        """
        Send a new order.
        
        Args:
            symbol: Symbol to trade (e.g., "600519.SH")
            side: Order side (buy/sell)
            quantity: Order quantity
            price: Limit price (required for limit orders)
            order_type: Order type (market/limit/stop)
            time_in_force: Time in force
            strategy_id: Strategy identifier for tracking
            **kwargs: Additional order parameters
            
        Returns:
            client_order_id for tracking
            
        Raises:
            RuntimeError: If gateway not connected
            ValueError: If order validation fails
        """
        if not self.is_connected:
            raise RuntimeError("Gateway not connected")
        
        # Normalize enums
        if isinstance(side, str):
            side = OrderSide(side.lower())
        if isinstance(order_type, str):
            order_type = OrderType(order_type.lower())
        
        # Rate limiting
        self._rate_limit()
        
        # Generate client order ID
        client_order_id = self._generate_order_id()
        
        # Create order request
        request = OrderRequest(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            order_type=order_type,
            time_in_force=time_in_force,
            client_order_id=client_order_id,
            strategy_id=strategy_id,
            stop_loss=kwargs.get("stop_loss"),
            take_profit=kwargs.get("take_profit"),
            tags=kwargs.get("tags", {}),
        )
        
        self.log.info(
            "order_sending",
            client_order_id=client_order_id,
            symbol=symbol,
            side=side.value,
            quantity=quantity,
            price=price,
            order_type=order_type.value,
        )
        
        # Create initial order update
        order_update = OrderUpdate(
            client_order_id=client_order_id,
            broker_order_id="",
            symbol=symbol,
            side=side,
            status=OrderStatus.PENDING_SUBMIT,
            order_type=order_type,
            price=price or 0.0,
            quantity=quantity,
        )
        self._orders[client_order_id] = order_update
        
        # Publish pending event
        self._publish_event(GatewayEventType.ORDER_SUBMITTED, order_update)
        
        try:
            # Send to broker
            broker_order_id = self._do_send_order(request)
            
            if broker_order_id:
                # Update mappings
                self._client_to_broker[client_order_id] = broker_order_id
                self._broker_to_client[broker_order_id] = client_order_id
                
                # Update order
                order_update.broker_order_id = broker_order_id
                order_update.status = OrderStatus.SUBMITTED
                order_update.update_time = datetime.now()
                
                self._publish_event(GatewayEventType.ORDER_ACCEPTED, order_update)
                
                self.log.info(
                    "order_submitted",
                    client_order_id=client_order_id,
                    broker_order_id=broker_order_id,
                )
            
            return client_order_id
            
        except Exception as e:
            order_update.status = OrderStatus.ERROR
            order_update.error_msg = str(e)
            order_update.update_time = datetime.now()
            
            self._publish_event(GatewayEventType.ORDER_ERROR, order_update)
            
            self.log.error(
                "order_send_error",
                client_order_id=client_order_id,
                error=str(e),
            )
            raise
    
    def cancel_order(self, client_order_id: str) -> bool:
        """
        Cancel an order.
        
        Args:
            client_order_id: Client order ID to cancel
            
        Returns:
            True if cancel request submitted successfully
            
        Raises:
            RuntimeError: If gateway not connected
            ValueError: If order not found
        """
        if not self.is_connected:
            raise RuntimeError("Gateway not connected")
        
        broker_order_id = self._client_to_broker.get(client_order_id)
        if not broker_order_id:
            raise ValueError(f"Order not found: {client_order_id}")
        
        order = self._orders.get(client_order_id)
        if not order:
            raise ValueError(f"Order not found: {client_order_id}")
        
        if order.status not in (OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED):
            self.log.warning(
                "order_cancel_invalid_status",
                client_order_id=client_order_id,
                status=order.status.value,
            )
            return False
        
        self.log.info(
            "order_cancelling",
            client_order_id=client_order_id,
            broker_order_id=broker_order_id,
        )
        
        # Update status
        order.status = OrderStatus.CANCEL_PENDING
        order.update_time = datetime.now()
        
        try:
            success = self._do_cancel_order(broker_order_id, client_order_id)
            return success
        except Exception as e:
            self.log.error(
                "order_cancel_error",
                client_order_id=client_order_id,
                error=str(e),
            )
            raise
    
    def cancel_all_orders(self, symbol: Optional[str] = None) -> int:
        """
        Cancel all open orders.
        
        Args:
            symbol: Optional symbol filter
            
        Returns:
            Number of cancel requests submitted
        """
        count = 0
        for order_id, order in list(self._orders.items()):
            if order.status in (OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED):
                if symbol is None or order.symbol == symbol:
                    try:
                        self.cancel_order(order_id)
                        count += 1
                    except Exception as e:
                        self.log.error(
                            "cancel_all_error",
                            order_id=order_id,
                            error=str(e),
                        )
        return count
    
    def get_order(self, client_order_id: str) -> Optional[OrderUpdate]:
        """Get order by client order ID."""
        return self._orders.get(client_order_id)
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[OrderUpdate]:
        """Get all open orders."""
        orders = []
        for order in self._orders.values():
            if order.status in (OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED):
                if symbol is None or order.symbol == symbol:
                    orders.append(order)
        return orders
    
    # ---------------------------------------------------------------------------
    # Query Methods
    # ---------------------------------------------------------------------------
    
    def query_account(self) -> Optional[AccountUpdate]:
        """Query current account information."""
        if not self.is_connected:
            return None
        
        try:
            return self._do_query_account()
        except Exception as e:
            self.log.error("query_account_error", error=str(e))
            return None
    
    def query_positions(self) -> List[PositionUpdate]:
        """Query all positions."""
        if not self.is_connected:
            return []
        
        try:
            return self._do_query_positions()
        except Exception as e:
            self.log.error("query_positions_error", error=str(e))
            return []
    
    def query_position(self, symbol: str) -> Optional[PositionUpdate]:
        """Query position for a specific symbol."""
        positions = self.query_positions()
        for pos in positions:
            if pos.symbol == symbol:
                return pos
        return None
    
    # ---------------------------------------------------------------------------
    # Callback Registration
    # ---------------------------------------------------------------------------
    
    def on_order(self, callback: Callable[[OrderUpdate], None]) -> None:
        """Register order update callback."""
        self._order_callbacks.append(callback)
    
    def on_trade(self, callback: Callable[[TradeUpdate], None]) -> None:
        """Register trade update callback."""
        self._trade_callbacks.append(callback)
    
    # ---------------------------------------------------------------------------
    # Internal Event Handling
    # ---------------------------------------------------------------------------
    
    def _on_order_update(self, update: OrderUpdate) -> None:
        """
        Handle order update from broker callback.
        
        Called by subclass when receiving order updates.
        """
        # Map broker order ID to client order ID
        client_order_id = update.client_order_id
        if not client_order_id and update.broker_order_id:
            client_order_id = self._broker_to_client.get(update.broker_order_id, "")
            update.client_order_id = client_order_id
        
        if not client_order_id:
            self.log.warning(
                "unknown_order_update",
                broker_order_id=update.broker_order_id,
            )
            return
        
        # Update local order cache
        if client_order_id in self._orders:
            existing = self._orders[client_order_id]
            existing.status = update.status
            existing.filled_quantity = update.filled_quantity
            existing.avg_fill_price = update.avg_fill_price
            existing.update_time = update.update_time
            existing.error_code = update.error_code
            existing.error_msg = update.error_msg
            update = existing
        else:
            self._orders[client_order_id] = update
        
        # Update broker order ID mapping
        if update.broker_order_id and client_order_id not in self._client_to_broker:
            self._client_to_broker[client_order_id] = update.broker_order_id
            self._broker_to_client[update.broker_order_id] = client_order_id
        
        # Publish appropriate event
        event_type = self._get_order_event_type(update.status)
        self._publish_event(event_type, update)
        
        # Invoke callbacks
        for cb in self._order_callbacks:
            try:
                cb(update)
            except Exception as e:
                self.log.error("order_callback_error", error=str(e))
        
        self.log.debug(
            "order_update_processed",
            client_order_id=client_order_id,
            status=update.status.value,
        )
    
    def _on_trade_update(self, update: TradeUpdate) -> None:
        """
        Handle trade update from broker callback.
        
        Called by subclass when receiving trade updates.
        """
        # Deduplicate trades
        if update.trade_id in self._processed_trades:
            self.log.debug("trade_duplicate_ignored", trade_id=update.trade_id)
            return
        self._processed_trades.add(update.trade_id)
        
        # Map broker order ID to client order ID
        if not update.client_order_id and update.broker_order_id:
            update.client_order_id = self._broker_to_client.get(
                update.broker_order_id, ""
            )
        
        # Publish event
        self._publish_event(GatewayEventType.TRADE_EXECUTED, update)
        
        # Invoke callbacks
        for cb in self._trade_callbacks:
            try:
                cb(update)
            except Exception as e:
                self.log.error("trade_callback_error", error=str(e))
        
        self.log.info(
            "trade_executed",
            trade_id=update.trade_id,
            symbol=update.symbol,
            side=update.side.value,
            price=update.price,
            quantity=update.quantity,
        )
    
    def _get_order_event_type(self, status: OrderStatus) -> str:
        """Map order status to event type."""
        mapping = {
            OrderStatus.SUBMITTED: GatewayEventType.ORDER_ACCEPTED,
            OrderStatus.PARTIALLY_FILLED: GatewayEventType.ORDER_PARTIAL,
            OrderStatus.FILLED: GatewayEventType.ORDER_FILLED,
            OrderStatus.CANCELLED: GatewayEventType.ORDER_CANCELLED,
            OrderStatus.REJECTED: GatewayEventType.ORDER_REJECTED,
            OrderStatus.ERROR: GatewayEventType.ORDER_ERROR,
        }
        return mapping.get(status, GatewayEventType.ORDER_SUBMITTED)
    
    # ---------------------------------------------------------------------------
    # Utilities
    # ---------------------------------------------------------------------------
    
    def _generate_order_id(self) -> str:
        """Generate unique client order ID."""
        with self._order_seq_lock:
            self._order_seq += 1
            return f"{self.config.broker.upper()}-{self._order_seq:08d}"
    
    def _rate_limit(self) -> None:
        """Apply rate limiting between orders."""
        now = time.time()
        elapsed = now - self._last_order_time
        
        if elapsed < self._order_interval:
            sleep_time = self._order_interval - elapsed
            time.sleep(sleep_time)
        
        self._last_order_time = time.time()
    
    def _publish_event(self, event_type: str, data: Any) -> None:
        """Publish event to queue."""
        event = {
            "type": event_type,
            "gateway": self.gateway_name,
            "timestamp": datetime.now().isoformat(),
            "data": data,
        }
        self.event_queue.put(event)
    
    # ---------------------------------------------------------------------------
    # Abstract Methods (must be implemented by subclasses)
    # ---------------------------------------------------------------------------
    
    @abstractmethod
    def _do_connect(self) -> bool:
        """
        Perform broker-specific connection.
        
        Returns:
            True if connection successful
        """
        ...
    
    @abstractmethod
    def _do_disconnect(self) -> None:
        """Perform broker-specific disconnection."""
        ...
    
    @abstractmethod
    def _do_send_order(self, request: OrderRequest) -> str:
        """
        Send order to broker.
        
        Args:
            request: Order request
            
        Returns:
            broker_order_id
        """
        ...
    
    @abstractmethod
    def _do_cancel_order(
        self, 
        broker_order_id: str, 
        client_order_id: str
    ) -> bool:
        """
        Cancel order at broker.
        
        Args:
            broker_order_id: Broker's order ID
            client_order_id: Client's order ID
            
        Returns:
            True if cancel request sent successfully
        """
        ...
    
    @abstractmethod
    def _do_query_account(self) -> Optional[AccountUpdate]:
        """Query account information from broker."""
        ...
    
    @abstractmethod
    def _do_query_positions(self) -> List[PositionUpdate]:
        """Query all positions from broker."""
        ...
    
    @abstractmethod
    def _do_query_orders(self) -> List[OrderUpdate]:
        """Query open orders from broker."""
        ...


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    # Classes
    "BaseLiveGateway",
    "GatewayConfig",
    "GatewayStatus",
    "OrderStatus",
    "OrderType",
    "OrderSide",
    "TimeInForce",
    "OrderRequest",
    "OrderUpdate",
    "TradeUpdate",
    "AccountUpdate",
    "PositionUpdate",
    "GatewayEventType",
]
