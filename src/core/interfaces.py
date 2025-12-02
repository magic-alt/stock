"""
Unified Interface Definitions

Centralized Protocol definitions for the quantitative trading platform.
All core interfaces and type hints are defined here to avoid circular imports.

V3.0.0: Initial release - consolidates interfaces from events.py, gateway.py
"""
from __future__ import annotations

from typing import Protocol, Iterable, Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
import pandas as pd


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Side(str, Enum):
    """Order side enumeration."""
    BUY = "buy"
    SELL = "sell"


class OrderTypeEnum(str, Enum):
    """Order type enumeration."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderStatusEnum(str, Enum):
    """Order status enumeration."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


# ---------------------------------------------------------------------------
# Data Transfer Objects
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class BarData:
    """
    OHLCV Bar data container.
    
    Standard representation for price bar data across all modules.
    """
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    open_interest: float = 0.0  # For futures
    
    def to_series(self) -> pd.Series:
        """Convert to pandas Series."""
        return pd.Series({
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        })
    
    @classmethod
    def from_series(cls, symbol: str, timestamp: datetime, series: pd.Series) -> "BarData":
        """Create BarData from pandas Series."""
        return cls(
            symbol=symbol,
            timestamp=timestamp,
            open=float(series.get("open", 0)),
            high=float(series.get("high", 0)),
            low=float(series.get("low", 0)),
            close=float(series.get("close", 0)),
            volume=float(series.get("volume", 0)),
        )


@dataclass(slots=True)
class TickData:
    """
    Tick-level market data container.
    """
    symbol: str
    timestamp: datetime
    last_price: float
    volume: float = 0.0
    bid_price: float = 0.0
    ask_price: float = 0.0
    bid_volume: float = 0.0
    ask_volume: float = 0.0


@dataclass
class PositionInfo:
    """Position information for a symbol."""
    symbol: str
    size: float = 0.0  # Positive for long, negative for short
    avg_price: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    
    @property
    def is_long(self) -> bool:
        return self.size > 0
    
    @property
    def is_short(self) -> bool:
        return self.size < 0
    
    @property
    def is_flat(self) -> bool:
        return self.size == 0


@dataclass
class AccountInfo:
    """Account information container."""
    account_id: str = "default"
    cash: float = 100000.0
    total_value: float = 100000.0
    available: float = 100000.0
    margin: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    
    @property
    def equity(self) -> float:
        return self.total_value
    
    @property
    def pnl_pct(self) -> float:
        initial = self.total_value - self.unrealized_pnl - self.realized_pnl
        if initial == 0:
            return 0.0
        return (self.realized_pnl + self.unrealized_pnl) / initial * 100


@dataclass
class OrderInfo:
    """Order information container."""
    order_id: str
    symbol: str
    side: Side
    order_type: OrderTypeEnum
    price: Optional[float]
    quantity: float
    filled_quantity: float = 0.0
    avg_fill_price: float = 0.0
    status: OrderStatusEnum = OrderStatusEnum.PENDING
    create_time: Optional[datetime] = None
    update_time: Optional[datetime] = None
    
    @property
    def is_active(self) -> bool:
        return self.status in (OrderStatusEnum.PENDING, OrderStatusEnum.SUBMITTED, OrderStatusEnum.PARTIAL)
    
    @property
    def remaining(self) -> float:
        return self.quantity - self.filled_quantity


@dataclass
class TradeInfo:
    """Trade execution information."""
    trade_id: str
    order_id: str
    symbol: str
    side: Side
    price: float
    quantity: float
    commission: float = 0.0
    timestamp: Optional[datetime] = None
    
    @property
    def value(self) -> float:
        return self.price * self.quantity


# ---------------------------------------------------------------------------
# Event Protocol
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class Event:
    """
    Event object for the event-driven architecture.
    
    Attributes:
        type: Event type identifier
        data: Associated payload data
    """
    type: str
    data: Any = None


class EventHandler(Protocol):
    """Protocol for event handlers."""
    def __call__(self, event: Event) -> None:
        """Handle an event."""
        ...


class EventEngineProtocol(Protocol):
    """Protocol for event engine implementations."""
    
    def register(self, event_type: str, handler: EventHandler) -> None:
        """Register a handler for an event type."""
        ...
    
    def unregister(self, event_type: str, handler: EventHandler) -> None:
        """Unregister a handler."""
        ...
    
    def put(self, event: Event) -> None:
        """Publish an event."""
        ...
    
    def start(self) -> None:
        """Start the event engine."""
        ...
    
    def stop(self) -> None:
        """Stop the event engine."""
        ...


# ---------------------------------------------------------------------------
# Gateway Protocols
# ---------------------------------------------------------------------------

class HistoryGateway(Protocol):
    """
    Protocol for historical data providers.
    
    Implementations:
    - BacktestGateway: Uses existing data_sources providers
    - PaperGateway: Fetches real-time historical snapshots
    """
    
    def load_bars(
        self, 
        symbols: Iterable[str], 
        start: str, 
        end: str, 
        adj: Optional[str] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        Load OHLCV bar data for multiple symbols.
        
        Args:
            symbols: List of symbols (e.g., ["600519.SH", "000333.SZ"])
            start: Start date in YYYY-MM-DD format
            end: End date in YYYY-MM-DD format
            adj: Adjustment type ("hfq", "qfq", "noadj", None)
            
        Returns:
            Dictionary mapping symbol to DataFrame with columns:
            [date, open, high, low, close, volume]
        """
        ...
    
    def load_index_nav(
        self, 
        index_code: str, 
        start: str, 
        end: str
    ) -> pd.Series:
        """
        Load index NAV series for benchmark comparison.
        
        Args:
            index_code: Index symbol (e.g., "000300.SH")
            start: Start date
            end: End date
            
        Returns:
            Series with DatetimeIndex and NAV values
        """
        ...


class TradeGateway(Protocol):
    """
    Protocol for order execution and account queries.
    
    Implementations:
    - BacktestGateway: Uses Backtrader broker
    - PaperGateway: Simulated matching engine
    - LiveGateway: Real broker API (IB/CTP/Binance)
    """
    
    def send_order(
        self, 
        symbol: str, 
        side: str, 
        size: float, 
        price: Optional[float] = None,
        order_type: str = "market"
    ) -> str:
        """
        Send a new order.
        
        Args:
            symbol: Symbol to trade
            side: "buy" or "sell"
            size: Order size
            price: Limit price (None for market orders)
            order_type: "market", "limit", "stop"
            
        Returns:
            Order ID
        """
        ...
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a pending order.
        
        Args:
            order_id: Order identifier
            
        Returns:
            True if cancellation was submitted successfully
        """
        ...
    
    def query_account(self) -> Dict[str, Any]:
        """
        Query account information.
        
        Returns:
            Dictionary with keys: balance, equity, available, etc.
        """
        ...
    
    def query_position(self, symbol: str) -> Dict[str, Any]:
        """
        Query position for a specific symbol.
        
        Args:
            symbol: Symbol to query
            
        Returns:
            Dictionary with keys: symbol, size, avg_price, market_value, etc.
        """
        ...
    
    def query_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Query active orders.
        
        Args:
            symbol: Filter by symbol (None for all orders)
            
        Returns:
            List of order dictionaries
        """
        ...


# ---------------------------------------------------------------------------
# Strategy Context Protocol
# ---------------------------------------------------------------------------

class StrategyContext(Protocol):
    """
    Unified context interface for strategy execution.
    
    Provides framework-independent access to:
    - Market data (current prices, history)
    - Order management (buy, sell, cancel)
    - Position/Account information
    
    This allows strategies to work across different execution engines
    (Backtrader, PaperRunner, LiveTrader) without modification.
    """
    
    # Account & Position Information
    @property
    def account(self) -> AccountInfo:
        """Get account information."""
        ...
    
    @property
    def positions(self) -> Dict[str, PositionInfo]:
        """Get all positions."""
        ...
    
    # Market Data Access
    def current_price(self, symbol: str, field: str = "close") -> Optional[float]:
        """
        Get current price for a symbol.
        
        Args:
            symbol: Symbol identifier
            field: Price field ("open", "high", "low", "close")
        
        Returns:
            Current price or None if not available
        """
        ...
    
    def get_bar(self, symbol: str) -> Optional[BarData]:
        """
        Get current bar data for a symbol.
        
        Args:
            symbol: Symbol identifier
            
        Returns:
            Current BarData or None
        """
        ...
    
    def history(
        self, 
        symbol: str, 
        fields: List[str], 
        periods: int,
        frequency: str = "1d"
    ) -> pd.DataFrame:
        """
        Get historical data for a symbol.
        
        Args:
            symbol: Symbol identifier
            fields: List of fields to retrieve
            periods: Number of periods to look back
            frequency: Data frequency ("1d", "1h", "5m", etc.)
        
        Returns:
            DataFrame with requested fields and periods
        """
        ...
    
    # Order Management
    def buy(
        self, 
        symbol: str, 
        size: Optional[float] = None,
        price: Optional[float] = None,
        order_type: str = "market"
    ) -> str:
        """
        Send buy order.
        
        Args:
            symbol: Symbol to buy
            size: Order size (None for auto-sizing)
            price: Limit price (None for market order)
            order_type: "market" or "limit"
        
        Returns:
            Order ID
        """
        ...
    
    def sell(
        self, 
        symbol: str, 
        size: Optional[float] = None,
        price: Optional[float] = None,
        order_type: str = "market"
    ) -> str:
        """
        Send sell order.
        
        Args:
            symbol: Symbol to sell
            size: Order size (None for full position)
            price: Limit price (None for market order)
            order_type: "market" or "limit"
        
        Returns:
            Order ID
        """
        ...
    
    def cancel(self, order_id: str) -> bool:
        """
        Cancel an order.
        
        Args:
            order_id: Order ID to cancel
        
        Returns:
            True if successful
        """
        ...
    
    # Utility Methods
    def log(self, message: str, level: str = "info") -> None:
        """Log a message."""
        ...
    
    def get_datetime(self) -> datetime:
        """Get current bar datetime."""
        ...


# ---------------------------------------------------------------------------
# Strategy Protocol
# ---------------------------------------------------------------------------

class BaseStrategyProtocol(Protocol):
    """
    Unified strategy interface protocol.
    
    Lifecycle methods:
    - on_init(ctx): Initialize indicators and state
    - on_start(ctx): Strategy starts
    - on_bar(ctx, bar): Process each bar
    - on_stop(ctx): Strategy stops
    """
    
    params: Dict[str, Any]
    
    def on_init(self, ctx: StrategyContext) -> None:
        """Initialize strategy state and indicators."""
        ...
    
    def on_start(self, ctx: StrategyContext) -> None:
        """Called when strategy starts."""
        ...
    
    def on_bar(self, ctx: StrategyContext, bar: BarData) -> None:
        """Process each bar - main strategy logic."""
        ...
    
    def on_stop(self, ctx: StrategyContext) -> None:
        """Called when strategy stops."""
        ...


# ---------------------------------------------------------------------------
# Risk Manager Protocol
# ---------------------------------------------------------------------------

class RiskManagerProtocol(Protocol):
    """Protocol for risk management implementations."""
    
    def check_order(
        self,
        symbol: str,
        side: str,
        size: float,
        price: float,
        account: AccountInfo,
        positions: Dict[str, PositionInfo]
    ) -> tuple[bool, str]:
        """
        Check if an order passes risk rules.
        
        Args:
            symbol: Symbol to trade
            side: Order side
            size: Order size
            price: Order price
            account: Current account state
            positions: Current positions
            
        Returns:
            Tuple of (passed, reason)
        """
        ...
    
    def calculate_position_size(
        self,
        symbol: str,
        side: str,
        price: float,
        account: AccountInfo,
        risk_per_trade: float = 0.02
    ) -> float:
        """
        Calculate appropriate position size based on risk parameters.
        
        Args:
            symbol: Symbol to trade
            side: Order side
            price: Entry price
            account: Current account state
            risk_per_trade: Maximum risk per trade as fraction of equity
            
        Returns:
            Recommended position size
        """
        ...
