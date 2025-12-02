"""
Live Trading Gateway Interfaces

Stubs and base classes for connecting to real broker APIs.
Implementations can be created for:
- CTP (China Futures)
- Interactive Brokers (Global)
- XtQuant/QMT (A-Share)
- Binance (Crypto)

V3.0.0: Initial interface definitions with CTP and IB stubs.

Usage:
    >>> from src.core.live_gateway import CTPGateway
    >>> 
    >>> gateway = CTPGateway(
    ...     event_engine=events,
    ...     broker_id="9999",
    ...     user_id="your_user",
    ...     password="your_pass",
    ...     front_address="tcp://180.168.146.187:10130"  # SimNow
    ... )
    >>> gateway.connect()
    >>> gateway.send_order("IF2401", "buy", 1, price=3500.0)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from src.core.events import EventEngine, Event, EventType
from src.core.interfaces import TradeGateway, AccountInfo, PositionInfo, OrderInfo, Side
from src.core.logger import get_logger

logger = get_logger("gateway")


# ---------------------------------------------------------------------------
# Gateway Status
# ---------------------------------------------------------------------------

class GatewayStatus(Enum):
    """Gateway connection status."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATED = "authenticated"
    ERROR = "error"


@dataclass
class GatewayConfig:
    """Base configuration for live gateways."""
    gateway_name: str
    api_key: str = ""
    secret: str = ""
    passphrase: str = ""  # For some exchanges
    testnet: bool = True  # Use testnet/sandbox by default


# ---------------------------------------------------------------------------
# Base Live Gateway
# ---------------------------------------------------------------------------

class BaseLiveGateway(ABC):
    """
    Abstract base class for live trading gateways.
    
    All live gateway implementations should inherit from this class
    and implement the abstract methods.
    
    Lifecycle:
        1. __init__(): Configure gateway
        2. connect(): Connect to broker API
        3. subscribe(): Subscribe to market data
        4. send_order() / cancel_order(): Trade
        5. disconnect(): Clean shutdown
    
    Events Published:
        - gateway.connected: When connection is established
        - gateway.disconnected: When connection is lost
        - gateway.error: When an error occurs
        - order.submitted: When order is submitted
        - order.filled: When order is filled
        - trade.executed: When trade occurs
    """
    
    def __init__(
        self,
        event_engine: EventEngine,
        gateway_name: str = "LIVE",
    ):
        """
        Initialize live gateway.
        
        Args:
            event_engine: Event engine for publishing events
            gateway_name: Identifier for this gateway instance
        """
        self.event_engine = event_engine
        self.gateway_name = gateway_name
        self.status = GatewayStatus.DISCONNECTED
        
        # Internal state
        self._orders: Dict[str, OrderInfo] = {}
        self._positions: Dict[str, PositionInfo] = {}
        self._account: Optional[AccountInfo] = None
        
        # Callbacks
        self._on_tick_callbacks: List[Callable] = []
        self._on_order_callbacks: List[Callable] = []
        self._on_trade_callbacks: List[Callable] = []
    
    # ---------------------------------------------------------------------------
    # Connection Management
    # ---------------------------------------------------------------------------
    
    @abstractmethod
    def connect(self) -> bool:
        """
        Connect to broker API.
        
        Returns:
            True if connection initiated successfully
        """
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from broker API."""
        pass
    
    def is_connected(self) -> bool:
        """Check if gateway is connected."""
        return self.status in (GatewayStatus.CONNECTED, GatewayStatus.AUTHENTICATED)
    
    # ---------------------------------------------------------------------------
    # Market Data
    # ---------------------------------------------------------------------------
    
    @abstractmethod
    def subscribe(self, symbols: List[str]) -> None:
        """
        Subscribe to market data for symbols.
        
        Args:
            symbols: List of symbols to subscribe
        """
        pass
    
    @abstractmethod
    def unsubscribe(self, symbols: List[str]) -> None:
        """
        Unsubscribe from market data.
        
        Args:
            symbols: List of symbols to unsubscribe
        """
        pass
    
    # ---------------------------------------------------------------------------
    # Trading (TradeGateway Protocol)
    # ---------------------------------------------------------------------------
    
    @abstractmethod
    def send_order(
        self,
        symbol: str,
        side: str,
        size: float,
        price: Optional[float] = None,
        order_type: str = "limit"
    ) -> str:
        """
        Send a new order.
        
        Args:
            symbol: Symbol to trade
            side: "buy" or "sell"
            size: Order size
            price: Limit price (None for market)
            order_type: "market", "limit", "stop"
            
        Returns:
            Order ID
        """
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order.
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            True if cancellation submitted
        """
        pass
    
    @abstractmethod
    def query_account(self) -> Dict[str, Any]:
        """Query account information."""
        pass
    
    @abstractmethod
    def query_position(self, symbol: str) -> Dict[str, Any]:
        """Query position for a symbol."""
        pass
    
    def query_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Query active orders."""
        result = []
        for order in self._orders.values():
            if symbol is None or order.symbol == symbol:
                result.append({
                    "order_id": order.order_id,
                    "symbol": order.symbol,
                    "side": order.side.value,
                    "price": order.price,
                    "quantity": order.quantity,
                    "status": order.status.value,
                })
        return result
    
    # ---------------------------------------------------------------------------
    # Event Publishing
    # ---------------------------------------------------------------------------
    
    def _publish_event(self, event_type: str, data: Any) -> None:
        """Publish an event to the event engine."""
        self.event_engine.put(Event(event_type, data))
    
    def _on_connected(self) -> None:
        """Handle connection established."""
        self.status = GatewayStatus.CONNECTED
        logger.info("Gateway connected", gateway=self.gateway_name)
        self._publish_event("gateway.connected", {"gateway": self.gateway_name})
    
    def _on_disconnected(self, reason: str = "") -> None:
        """Handle disconnection."""
        self.status = GatewayStatus.DISCONNECTED
        logger.warning("Gateway disconnected", gateway=self.gateway_name, reason=reason)
        self._publish_event("gateway.disconnected", {"gateway": self.gateway_name, "reason": reason})
    
    def _on_error(self, error: str) -> None:
        """Handle error."""
        self.status = GatewayStatus.ERROR
        logger.error("Gateway error", gateway=self.gateway_name, error=error)
        self._publish_event("gateway.error", {"gateway": self.gateway_name, "error": error})


# ---------------------------------------------------------------------------
# CTP Gateway Stub (China Futures)
# ---------------------------------------------------------------------------

class CTPGateway(BaseLiveGateway):
    """
    CTP Gateway for China Futures Trading.
    
    This is a stub implementation. For production use, integrate with:
    - openctp (https://github.com/openctp/openctp)
    - vnpy_ctp (https://github.com/vnpy/vnpy_ctp)
    
    SimNow Test Environment:
    - Front: tcp://180.168.146.187:10130 (Trade)
    - MD Front: tcp://180.168.146.187:10131 (Market Data)
    - Broker ID: 9999
    
    Usage:
        >>> gateway = CTPGateway(
        ...     event_engine=events,
        ...     broker_id="9999",
        ...     user_id="your_simnow_account",
        ...     password="your_password",
        ...     front_address="tcp://180.168.146.187:10130"
        ... )
        >>> gateway.connect()
    """
    
    def __init__(
        self,
        event_engine: EventEngine,
        broker_id: str,
        user_id: str,
        password: str,
        front_address: str,
        md_address: Optional[str] = None,
        app_id: str = "",
        auth_code: str = "",
    ):
        """
        Initialize CTP gateway.
        
        Args:
            event_engine: Event engine
            broker_id: Broker ID (e.g., "9999" for SimNow)
            user_id: Trading account
            password: Password
            front_address: Trade front address
            md_address: Market data front address
            app_id: App ID for authentication
            auth_code: Auth code for authentication
        """
        super().__init__(event_engine, "CTP")
        
        self.broker_id = broker_id
        self.user_id = user_id
        self.password = password
        self.front_address = front_address
        self.md_address = md_address or front_address.replace("10130", "10131")
        self.app_id = app_id
        self.auth_code = auth_code
        
        # CTP API instances (to be initialized)
        self._td_api = None  # Trade API
        self._md_api = None  # Market Data API
        
        self._order_ref = 0
    
    def connect(self) -> bool:
        """Connect to CTP front server."""
        logger.info(
            "Connecting to CTP",
            front=self.front_address,
            broker=self.broker_id,
            user=self.user_id
        )
        
        # Stub: In real implementation, initialize CTP API
        # self._td_api = CThostFtdcTraderApi.CreateFtdcTraderApi()
        # self._td_api.RegisterSpi(self)
        # self._td_api.RegisterFront(self.front_address)
        # self._td_api.Init()
        
        # Simulate successful connection
        self._on_connected()
        return True
    
    def disconnect(self) -> None:
        """Disconnect from CTP."""
        logger.info("Disconnecting from CTP", gateway=self.gateway_name)
        
        # Stub: Release API
        # if self._td_api:
        #     self._td_api.Release()
        
        self._on_disconnected("Manual disconnect")
    
    def subscribe(self, symbols: List[str]) -> None:
        """Subscribe to market data."""
        logger.info("Subscribing to CTP market data", symbols=symbols)
        
        # Stub: Subscribe via MD API
        # self._md_api.SubscribeMarketData(symbols)
    
    def unsubscribe(self, symbols: List[str]) -> None:
        """Unsubscribe from market data."""
        logger.info("Unsubscribing from CTP market data", symbols=symbols)
    
    def send_order(
        self,
        symbol: str,
        side: str,
        size: float,
        price: Optional[float] = None,
        order_type: str = "limit"
    ) -> str:
        """Send order via CTP."""
        if not self.is_connected():
            logger.error("CTP not connected", action="send_order")
            return ""
        
        self._order_ref += 1
        order_id = f"CTP-{self._order_ref:08d}"
        
        logger.info(
            "Sending CTP order",
            order_id=order_id,
            symbol=symbol,
            side=side,
            size=size,
            price=price,
            order_type=order_type
        )
        
        # Stub: In real implementation, construct CThostFtdcInputOrderField
        # and call self._td_api.ReqOrderInsert()
        
        return order_id
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel order via CTP."""
        logger.info("Cancelling CTP order", order_id=order_id)
        
        # Stub: Call ReqOrderAction
        return True
    
    def query_account(self) -> Dict[str, Any]:
        """Query account from CTP."""
        # Stub: Return simulated account
        return {
            "account_id": self.user_id,
            "balance": 1000000.0,
            "available": 800000.0,
            "frozen": 200000.0,
            "equity": 1000000.0,
        }
    
    def query_position(self, symbol: str) -> Dict[str, Any]:
        """Query position from CTP."""
        return {
            "symbol": symbol,
            "size": 0,
            "avg_price": 0,
            "market_value": 0,
        }


# ---------------------------------------------------------------------------
# IB Gateway Stub (Interactive Brokers)
# ---------------------------------------------------------------------------

class IBGateway(BaseLiveGateway):
    """
    Interactive Brokers Gateway.
    
    This is a stub implementation. For production use, integrate with:
    - ib_insync (https://github.com/erdewit/ib_insync)
    - ibapi (Official IB API)
    
    Requirements:
    - IB Gateway or TWS running
    - API connections enabled
    - Paper trading account for testing
    
    Usage:
        >>> gateway = IBGateway(
        ...     event_engine=events,
        ...     host="127.0.0.1",
        ...     port=7497,  # Paper trading port
        ...     client_id=1
        ... )
        >>> gateway.connect()
    """
    
    def __init__(
        self,
        event_engine: EventEngine,
        host: str = "127.0.0.1",
        port: int = 7497,  # 7497 for paper, 7496 for live
        client_id: int = 1,
    ):
        """
        Initialize IB gateway.
        
        Args:
            event_engine: Event engine
            host: TWS/Gateway host
            port: TWS/Gateway port (7497=paper, 7496=live)
            client_id: Client ID for this connection
        """
        super().__init__(event_engine, "IB")
        
        self.host = host
        self.port = port
        self.client_id = client_id
        
        # IB API instance
        self._ib = None  # ib_insync.IB instance
        
        self._order_id = 0
    
    def connect(self) -> bool:
        """Connect to IB TWS/Gateway."""
        logger.info(
            "Connecting to IB",
            host=self.host,
            port=self.port,
            client_id=self.client_id
        )
        
        # Stub: In real implementation
        # from ib_insync import IB
        # self._ib = IB()
        # self._ib.connect(self.host, self.port, clientId=self.client_id)
        
        self._on_connected()
        return True
    
    def disconnect(self) -> None:
        """Disconnect from IB."""
        logger.info("Disconnecting from IB")
        
        # Stub: self._ib.disconnect()
        
        self._on_disconnected("Manual disconnect")
    
    def subscribe(self, symbols: List[str]) -> None:
        """Subscribe to IB market data."""
        logger.info("Subscribing to IB market data", symbols=symbols)
        
        # Stub: Create contracts and subscribe
        # for symbol in symbols:
        #     contract = Stock(symbol, 'SMART', 'USD')
        #     self._ib.reqMktData(contract)
    
    def unsubscribe(self, symbols: List[str]) -> None:
        """Unsubscribe from IB market data."""
        logger.info("Unsubscribing from IB market data", symbols=symbols)
    
    def send_order(
        self,
        symbol: str,
        side: str,
        size: float,
        price: Optional[float] = None,
        order_type: str = "limit"
    ) -> str:
        """Send order via IB."""
        if not self.is_connected():
            logger.error("IB not connected", action="send_order")
            return ""
        
        self._order_id += 1
        order_id = f"IB-{self._order_id:08d}"
        
        logger.info(
            "Sending IB order",
            order_id=order_id,
            symbol=symbol,
            side=side,
            size=size,
            price=price,
            order_type=order_type
        )
        
        # Stub: In real implementation
        # contract = Stock(symbol, 'SMART', 'USD')
        # order = LimitOrder(side.upper(), size, price)
        # trade = self._ib.placeOrder(contract, order)
        
        return order_id
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel order via IB."""
        logger.info("Cancelling IB order", order_id=order_id)
        return True
    
    def query_account(self) -> Dict[str, Any]:
        """Query account from IB."""
        # Stub: self._ib.accountSummary()
        return {
            "account_id": f"IB-{self.client_id}",
            "balance": 100000.0,
            "available": 90000.0,
            "equity": 100000.0,
        }
    
    def query_position(self, symbol: str) -> Dict[str, Any]:
        """Query position from IB."""
        return {
            "symbol": symbol,
            "size": 0,
            "avg_price": 0,
            "market_value": 0,
        }


# ---------------------------------------------------------------------------
# XtQuant Gateway Stub (A-Share via QMT)
# ---------------------------------------------------------------------------

class XtQuantGateway(BaseLiveGateway):
    """
    XtQuant Gateway for A-Share Trading via QMT.
    
    This is a stub for future implementation.
    XtQuant is a popular choice for A-share retail trading.
    
    Requirements:
    - QMT client installed
    - xtquant package installed
    """
    
    def __init__(self, event_engine: EventEngine, account_id: str):
        super().__init__(event_engine, "XtQuant")
        self.account_id = account_id
    
    def connect(self) -> bool:
        logger.info("Connecting to XtQuant", account=self.account_id)
        self._on_connected()
        return True
    
    def disconnect(self) -> None:
        self._on_disconnected()
    
    def subscribe(self, symbols: List[str]) -> None:
        pass
    
    def unsubscribe(self, symbols: List[str]) -> None:
        pass
    
    def send_order(self, symbol: str, side: str, size: float,
                   price: Optional[float] = None, order_type: str = "limit") -> str:
        return f"XT-{symbol}-{side}"
    
    def cancel_order(self, order_id: str) -> bool:
        return True
    
    def query_account(self) -> Dict[str, Any]:
        return {"account_id": self.account_id, "balance": 0, "equity": 0}
    
    def query_position(self, symbol: str) -> Dict[str, Any]:
        return {"symbol": symbol, "size": 0}
