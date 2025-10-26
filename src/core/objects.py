"""
Standardized Data Objects

Unified data structures for market data, orders, trades, positions, and accounts.
Ensures type safety and consistency across all modules (simulation, backtest, live trading).

Design inspired by VN.py's data object standards with 30+ fields.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
import json


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Direction(str, Enum):
    """Order direction."""
    LONG = "long"  # Buy
    SHORT = "short"  # Sell
    
    def __str__(self) -> str:
        return self.value


class OrderType(str, Enum):
    """Order type."""
    MARKET = "market"  # Market order
    LIMIT = "limit"  # Limit order
    STOP = "stop"  # Stop order
    STOP_LIMIT = "stop_limit"  # Stop limit order
    
    def __str__(self) -> str:
        return self.value


class OrderStatus(str, Enum):
    """Order status."""
    PENDING = "pending"  # Order created but not submitted
    SUBMITTED = "submitted"  # Order submitted to exchange
    PARTIAL = "partial"  # Partially filled
    FILLED = "filled"  # Fully filled
    CANCELLED = "cancelled"  # Cancelled
    REJECTED = "rejected"  # Rejected by exchange/broker
    
    def __str__(self) -> str:
        return self.value


class Exchange(str, Enum):
    """Exchange identifier."""
    SSE = "SSE"  # Shanghai Stock Exchange
    SZSE = "SZSE"  # Shenzhen Stock Exchange
    SHFE = "SHFE"  # Shanghai Futures Exchange
    DCE = "DCE"  # Dalian Commodity Exchange
    CZCE = "CZCE"  # Zhengzhou Commodity Exchange
    CFFEX = "CFFEX"  # China Financial Futures Exchange
    INE = "INE"  # Shanghai International Energy Exchange
    
    def __str__(self) -> str:
        return self.value


# ---------------------------------------------------------------------------
# Market Data Objects
# ---------------------------------------------------------------------------

@dataclass
class BarData:
    """
    OHLCV bar data.
    
    Standard format for candlestick data across all frequencies.
    """
    # Identity
    symbol: str  # e.g., "600519.SH", "000001.SZ"
    datetime: datetime  # Bar timestamp
    exchange: Optional[Exchange] = None
    
    # OHLCV
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: float = 0.0
    
    # Additional fields
    open_interest: float = 0.0  # For futures
    turnover: float = 0.0  # Trading amount
    
    # Metadata
    interval: str = "1d"  # "1m", "5m", "1h", "1d", etc.
    gateway_name: str = ""  # Data source
    
    def __post_init__(self):
        """Validate data consistency."""
        if self.high < self.low:
            raise ValueError(f"Invalid bar: high {self.high} < low {self.low}")
        if self.high < max(self.open, self.close):
            self.high = max(self.open, self.close)
        if self.low > min(self.open, self.close):
            self.low = min(self.open, self.close)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "datetime": self.datetime.isoformat(),
            "exchange": str(self.exchange) if self.exchange else None,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "open_interest": self.open_interest,
            "turnover": self.turnover,
            "interval": self.interval,
            "gateway_name": self.gateway_name,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BarData:
        """Create from dictionary."""
        if isinstance(data.get("datetime"), str):
            data["datetime"] = datetime.fromisoformat(data["datetime"])
        if isinstance(data.get("exchange"), str):
            data["exchange"] = Exchange(data["exchange"])
        return cls(**data)


@dataclass
class TickData:
    """
    Tick data (Level 1 market data).
    
    Real-time price and volume data with bid/ask information.
    """
    # Identity
    symbol: str
    datetime: datetime
    exchange: Optional[Exchange] = None
    
    # Last trade
    last_price: float = 0.0
    last_volume: float = 0.0
    
    # Best bid/ask (Level 1)
    bid_price_1: float = 0.0
    bid_volume_1: float = 0.0
    ask_price_1: float = 0.0
    ask_volume_1: float = 0.0
    
    # Additional levels (Level 5)
    bid_price_2: float = 0.0
    bid_volume_2: float = 0.0
    bid_price_3: float = 0.0
    bid_volume_3: float = 0.0
    bid_price_4: float = 0.0
    bid_volume_4: float = 0.0
    bid_price_5: float = 0.0
    bid_volume_5: float = 0.0
    
    ask_price_2: float = 0.0
    ask_volume_2: float = 0.0
    ask_price_3: float = 0.0
    ask_volume_3: float = 0.0
    ask_price_4: float = 0.0
    ask_volume_4: float = 0.0
    ask_price_5: float = 0.0
    ask_volume_5: float = 0.0
    
    # Daily statistics
    open_price: float = 0.0
    high_price: float = 0.0
    low_price: float = 0.0
    pre_close: float = 0.0
    
    # Volume/Turnover
    volume: float = 0.0  # Total volume
    turnover: float = 0.0  # Total turnover
    open_interest: float = 0.0  # For futures
    
    # Metadata
    gateway_name: str = ""
    
    @property
    def mid_price(self) -> float:
        """Calculate mid price from best bid/ask."""
        if self.bid_price_1 > 0 and self.ask_price_1 > 0:
            return (self.bid_price_1 + self.ask_price_1) / 2.0
        return self.last_price
    
    @property
    def spread(self) -> float:
        """Calculate bid-ask spread."""
        if self.bid_price_1 > 0 and self.ask_price_1 > 0:
            return self.ask_price_1 - self.bid_price_1
        return 0.0


# ---------------------------------------------------------------------------
# Trading Objects
# ---------------------------------------------------------------------------

@dataclass
class OrderData:
    """
    Order information.
    
    Represents an order throughout its lifecycle.
    """
    # Identity
    symbol: str
    exchange: Optional[Exchange] = None
    order_id: str = ""  # Local order ID
    external_id: str = ""  # Exchange order ID
    
    # Order parameters
    direction: Direction = Direction.LONG
    order_type: OrderType = OrderType.MARKET
    price: float = 0.0  # Limit price (0 for market orders)
    volume: float = 0.0  # Order quantity
    traded: float = 0.0  # Filled quantity
    
    # Status
    status: OrderStatus = OrderStatus.PENDING
    
    # Timestamps
    datetime: datetime = field(default_factory=datetime.now)
    submitted_time: Optional[datetime] = None
    filled_time: Optional[datetime] = None
    cancelled_time: Optional[datetime] = None
    
    # Metadata
    strategy_name: str = ""
    gateway_name: str = ""
    reference: str = ""  # User-defined reference
    
    @property
    def remaining(self) -> float:
        """Calculate remaining quantity."""
        return self.volume - self.traded
    
    @property
    def is_active(self) -> bool:
        """Check if order is active (can be filled/cancelled)."""
        return self.status in (OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.PARTIAL)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "exchange": str(self.exchange) if self.exchange else None,
            "order_id": self.order_id,
            "external_id": self.external_id,
            "direction": str(self.direction),
            "order_type": str(self.order_type),
            "price": self.price,
            "volume": self.volume,
            "traded": self.traded,
            "status": str(self.status),
            "datetime": self.datetime.isoformat(),
            "submitted_time": self.submitted_time.isoformat() if self.submitted_time else None,
            "filled_time": self.filled_time.isoformat() if self.filled_time else None,
            "cancelled_time": self.cancelled_time.isoformat() if self.cancelled_time else None,
            "strategy_name": self.strategy_name,
            "gateway_name": self.gateway_name,
            "reference": self.reference,
        }


@dataclass
class TradeData:
    """
    Trade (fill) information.
    
    Represents an executed trade that fills an order.
    """
    # Identity
    symbol: str
    exchange: Optional[Exchange] = None
    trade_id: str = ""  # Exchange trade ID
    order_id: str = ""  # Associated order ID
    
    # Trade details
    direction: Direction = Direction.LONG
    price: float = 0.0  # Fill price
    volume: float = 0.0  # Fill quantity
    
    # Timestamp
    datetime: datetime = field(default_factory=datetime.now)
    
    # Metadata
    strategy_name: str = ""
    gateway_name: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "exchange": str(self.exchange) if self.exchange else None,
            "trade_id": self.trade_id,
            "order_id": self.order_id,
            "direction": str(self.direction),
            "price": self.price,
            "volume": self.volume,
            "datetime": self.datetime.isoformat(),
            "strategy_name": self.strategy_name,
            "gateway_name": self.gateway_name,
        }


@dataclass
class PositionData:
    """
    Position information.
    
    Tracks current holdings for a symbol.
    """
    # Identity
    symbol: str
    exchange: Optional[Exchange] = None
    
    # Position details
    direction: Direction = Direction.LONG  # Long or short
    volume: float = 0.0  # Position size
    frozen: float = 0.0  # Frozen quantity (in orders)
    
    # Cost tracking
    price: float = 0.0  # Average entry price
    cost: float = 0.0  # Total cost (including fees)
    
    # P&L
    pnl: float = 0.0  # Realized P&L
    unrealized_pnl: float = 0.0  # Unrealized P&L
    
    # Timestamp
    datetime: datetime = field(default_factory=datetime.now)
    
    # Metadata
    strategy_name: str = ""
    gateway_name: str = ""
    
    @property
    def available(self) -> float:
        """Calculate available quantity (not frozen)."""
        return self.volume - self.frozen
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "exchange": str(self.exchange) if self.exchange else None,
            "direction": str(self.direction),
            "volume": self.volume,
            "frozen": self.frozen,
            "price": self.price,
            "cost": self.cost,
            "pnl": self.pnl,
            "unrealized_pnl": self.unrealized_pnl,
            "datetime": self.datetime.isoformat(),
            "strategy_name": self.strategy_name,
            "gateway_name": self.gateway_name,
        }


@dataclass
class AccountData:
    """
    Account information.
    
    Tracks cash, margin, and overall account value.
    """
    # Identity
    account_id: str = ""
    
    # Cash
    balance: float = 0.0  # Total balance
    available: float = 0.0  # Available cash
    frozen: float = 0.0  # Frozen cash (in orders)
    
    # Margin (for futures/options)
    margin: float = 0.0  # Margin used
    margin_ratio: float = 0.0  # Margin ratio (margin / balance)
    
    # P&L
    realized_pnl: float = 0.0  # Realized profit/loss
    unrealized_pnl: float = 0.0  # Unrealized profit/loss
    
    # Timestamp
    datetime: datetime = field(default_factory=datetime.now)
    
    # Metadata
    gateway_name: str = ""
    
    @property
    def total_value(self) -> float:
        """Calculate total account value."""
        return self.balance + self.unrealized_pnl
    
    @property
    def risk_ratio(self) -> float:
        """Calculate risk ratio (used capital / total)."""
        if self.balance == 0:
            return 0.0
        return (self.frozen + self.margin) / self.balance
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "account_id": self.account_id,
            "balance": self.balance,
            "available": self.available,
            "frozen": self.frozen,
            "margin": self.margin,
            "margin_ratio": self.margin_ratio,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl,
            "datetime": self.datetime.isoformat(),
            "gateway_name": self.gateway_name,
        }


# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------

def parse_symbol(symbol: str) -> tuple[str, Optional[Exchange]]:
    """
    Parse symbol string to extract code and exchange.
    
    Args:
        symbol: Symbol string (e.g., "600519.SH", "000001.SZ")
    
    Returns:
        Tuple of (symbol_code, exchange)
    
    Examples:
        >>> parse_symbol("600519.SH")
        ("600519", Exchange.SSE)
        >>> parse_symbol("000001.SZ")
        ("000001", Exchange.SZSE)
        >>> parse_symbol("600519")
        ("600519", None)
    """
    if "." not in symbol:
        return symbol, None
    
    code, suffix = symbol.split(".", 1)
    
    exchange_map = {
        "SH": Exchange.SSE,
        "SS": Exchange.SSE,
        "SSE": Exchange.SSE,
        "SZ": Exchange.SZSE,
        "SZSE": Exchange.SZSE,
    }
    
    exchange = exchange_map.get(suffix.upper())
    return code, exchange


def format_symbol(code: str, exchange: Optional[Exchange]) -> str:
    """
    Format symbol with exchange suffix.
    
    Args:
        code: Symbol code
        exchange: Exchange identifier
    
    Returns:
        Formatted symbol string
    
    Examples:
        >>> format_symbol("600519", Exchange.SSE)
        "600519.SH"
        >>> format_symbol("000001", Exchange.SZSE)
        "000001.SZ"
    """
    if exchange is None:
        return code
    
    suffix_map = {
        Exchange.SSE: "SH",
        Exchange.SZSE: "SZ",
    }
    
    suffix = suffix_map.get(exchange, "")
    return f"{code}.{suffix}" if suffix else code


# ---------------------------------------------------------------------------
# JSON Serialization
# ---------------------------------------------------------------------------

class DataObjectEncoder(json.JSONEncoder):
    """Custom JSON encoder for data objects."""
    
    def default(self, obj):
        """Encode data objects."""
        if hasattr(obj, "to_dict"):
            return obj.to_dict()
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Enum):
            return str(obj)
        return super().default(obj)


def to_json(obj: Any) -> str:
    """Convert data object to JSON string."""
    return json.dumps(obj, cls=DataObjectEncoder, ensure_ascii=False, indent=2)
