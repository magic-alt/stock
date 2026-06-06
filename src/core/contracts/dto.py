"""V6 Open Platform domain DTOs.

These are the **single source of truth** for value objects exchanged between
the kernel, engines, adapters and plugins. They are:

* **frozen dataclasses** — immutable so they can be shared across threads
  and message-bus boundaries without defensive copies;
* **validated at construction** — invariants are enforced in
  :py:meth:`object.__post_init__`, so malformed objects cannot enter the
  system;
* **transport-friendly** — every type provides :py:meth:`to_dict` and
  :py:meth:`from_dict` so adapters can serialise without depending on a
  specific transport library.

Phase 2 freezes the V6 SDK surface; new fields added later MUST be
``Optional`` with safe defaults so existing plugins keep loading (see
:mod:`src.core.contracts.version`).

V5 modules (``src/core/interfaces.py``, ``src/core/objects.py``) are
intentionally **not** touched in this phase. The two type systems coexist
until Phase 3 introduces conversion shims at the engine boundary.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Mapping, Optional, Tuple


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AssetClass(str, Enum):
    EQUITY = "equity"
    FUTURE = "future"
    OPTION = "option"
    FX = "fx"
    CRYPTO = "crypto"
    INDEX = "index"
    BOND = "bond"
    FUND = "fund"


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderStatus(str, Enum):
    """Unified order status — single source of truth for all modules.

    Merges states from interfaces.py, order_state.py, objects.py, and
    simulation/order.py into one canonical enumeration.
    """
    CREATED = "created"
    PENDING = "pending"
    PENDING_SUBMIT = "pending_submit"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    PARTIALLY_FILLED = "partially_filled"
    PARTIAL = "partial"  # alias kept for backward compatibility
    FILLED = "filled"
    CANCEL_PENDING = "cancel_pending"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    ERROR = "error"


# Alias kept for modules that used the ``OrderStatusEnum`` name.
OrderStatusEnum = OrderStatus

# Mapping from legacy / broker string values to canonical OrderStatus members.
_ORDER_STATUS_ALIASES: dict[str, OrderStatus] = {
    "created": OrderStatus.CREATED,
    "pending": OrderStatus.PENDING,
    "pending_submit": OrderStatus.PENDING_SUBMIT,
    "submitted": OrderStatus.SUBMITTED,
    "accepted": OrderStatus.ACCEPTED,
    "partial": OrderStatus.PARTIALLY_FILLED,
    "partial_fill": OrderStatus.PARTIALLY_FILLED,
    "partial_filled": OrderStatus.PARTIALLY_FILLED,
    "partially_filled": OrderStatus.PARTIALLY_FILLED,
    "filled": OrderStatus.FILLED,
    "cancel_pending": OrderStatus.CANCEL_PENDING,
    "cancelled": OrderStatus.CANCELLED,
    "canceled": OrderStatus.CANCELLED,
    "rejected": OrderStatus.REJECTED,
    "error": OrderStatus.ERROR,
    "expired": OrderStatus.EXPIRED,
}


def normalize_order_status(status: OrderStatus | str) -> OrderStatus:
    """Return the canonical OrderStatus for legacy or broker status values."""
    if isinstance(status, OrderStatus):
        return status
    return _ORDER_STATUS_ALIASES.get(str(status).lower(), OrderStatus.CREATED)


def is_active_order_status(status: OrderStatus | str) -> bool:
    """Return True when an order status can still receive execution updates."""
    return normalize_order_status(status) in {
        OrderStatus.CREATED,
        OrderStatus.PENDING,
        OrderStatus.PENDING_SUBMIT,
        OrderStatus.SUBMITTED,
        OrderStatus.ACCEPTED,
        OrderStatus.PARTIALLY_FILLED,
    }


def is_terminal_order_status(status: OrderStatus | str) -> bool:
    """Return True when an order status is terminal."""
    return normalize_order_status(status) in {
        OrderStatus.FILLED,
        OrderStatus.CANCELLED,
        OrderStatus.REJECTED,
        OrderStatus.EXPIRED,
        OrderStatus.ERROR,
    }


class TimeInForce(str, Enum):
    DAY = "day"
    GTC = "gtc"           # good till cancelled
    IOC = "ioc"           # immediate or cancel
    FOK = "fok"           # fill or kill
    GTD = "gtd"           # good till date


class RiskDecision(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    THROTTLED = "throttled"
    REQUIRES_REVIEW = "requires_review"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_aware(ts: datetime) -> datetime:
    """Force a datetime to UTC-aware; raise if naive cannot be interpreted."""
    if ts.tzinfo is None:
        raise ValueError("Naive datetime not allowed in V6 contracts; pass a tz-aware value (UTC preferred)")
    return ts


def _normalize_amount(value: Any) -> Decimal:
    """Coerce any numeric/str amount to :class:`Decimal` with consistent precision."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise TypeError("bool is not a valid amount")
    if isinstance(value, (int, float, str)):
        return Decimal(str(value))
    raise TypeError(f"Unsupported amount type: {type(value).__name__}")


def _dump(value: Any) -> Any:
    """JSON-friendly recursive conversion for ``to_dict``."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return {f.name: _dump(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, (list, tuple)):
        return [_dump(v) for v in value]
    if isinstance(value, Mapping):
        return {str(k): _dump(v) for k, v in value.items()}
    return value


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Instrument:
    """Identifies a tradable instrument.

    ``symbol`` is the venue-local identifier (e.g. ``600519``); ``exchange``
    is the ISO MIC or venue code (e.g. ``XSHG``, ``XSHE``, ``CFFEX``);
    ``instrument_id`` is the canonical ``symbol.exchange`` form used as a
    key throughout the platform.
    """

    symbol: str
    exchange: str
    asset_class: AssetClass = AssetClass.EQUITY
    currency: str = "CNY"
    lot_size: int = 100
    tick_size: Decimal = Decimal("0.01")
    multiplier: int = 1
    name: Optional[str] = None
    expiry: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("Instrument.symbol must be non-empty")
        if not self.exchange:
            raise ValueError("Instrument.exchange must be non-empty")
        if self.lot_size <= 0:
            raise ValueError("Instrument.lot_size must be positive")
        if self.tick_size <= 0:
            raise ValueError("Instrument.tick_size must be positive")
        if self.multiplier <= 0:
            raise ValueError("Instrument.multiplier must be positive")
        if self.expiry is not None:
            object.__setattr__(self, "expiry", _ensure_aware(self.expiry))

    @property
    def instrument_id(self) -> str:
        return f"{self.symbol}.{self.exchange}"

    def to_dict(self) -> dict:
        return _dump(self)


# ---------------------------------------------------------------------------
# Market data
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Bar:
    """OHLCV bar at a fixed interval.

    ``interval`` follows the platform convention (``1m``, ``5m``, ``1d``).
    ``ts`` is the bar's **close** timestamp in UTC.
    """

    instrument_id: str
    ts: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    turnover: Optional[Decimal] = None
    interval: str = "1d"

    def __post_init__(self) -> None:
        object.__setattr__(self, "ts", _ensure_aware(self.ts))
        for fld in ("open", "high", "low", "close", "volume"):
            object.__setattr__(self, fld, _normalize_amount(getattr(self, fld)))
        if self.turnover is not None:
            object.__setattr__(self, "turnover", _normalize_amount(self.turnover))
        if self.high < self.low:
            raise ValueError(f"Bar.high ({self.high}) < Bar.low ({self.low})")
        if not (self.low <= self.open <= self.high):
            raise ValueError(f"Bar.open {self.open} not in [low={self.low}, high={self.high}]")
        if not (self.low <= self.close <= self.high):
            raise ValueError(f"Bar.close {self.close} not in [low={self.low}, high={self.high}]")
        if self.volume < 0:
            raise ValueError("Bar.volume must be non-negative")
        if not self.interval:
            raise ValueError("Bar.interval must be non-empty")

    def to_dict(self) -> dict:
        return _dump(self)


@dataclass(frozen=True, slots=True)
class Tick:
    """Last-trade tick."""

    instrument_id: str
    ts: datetime
    price: Decimal
    volume: Decimal
    bid: Optional[Decimal] = None
    ask: Optional[Decimal] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "ts", _ensure_aware(self.ts))
        object.__setattr__(self, "price", _normalize_amount(self.price))
        object.__setattr__(self, "volume", _normalize_amount(self.volume))
        if self.bid is not None:
            object.__setattr__(self, "bid", _normalize_amount(self.bid))
        if self.ask is not None:
            object.__setattr__(self, "ask", _normalize_amount(self.ask))
        if self.price < 0:
            raise ValueError("Tick.price must be non-negative")
        if self.volume < 0:
            raise ValueError("Tick.volume must be non-negative")

    def to_dict(self) -> dict:
        return _dump(self)


@dataclass(frozen=True, slots=True)
class BookLevel:
    price: Decimal
    size: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "price", _normalize_amount(self.price))
        object.__setattr__(self, "size", _normalize_amount(self.size))
        if self.size < 0:
            raise ValueError("BookLevel.size must be non-negative")


@dataclass(frozen=True, slots=True)
class OrderBookSnapshot:
    """Top-N level-2 snapshot."""

    instrument_id: str
    ts: datetime
    bids: Tuple[BookLevel, ...] = field(default_factory=tuple)
    asks: Tuple[BookLevel, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "ts", _ensure_aware(self.ts))
        object.__setattr__(self, "bids", tuple(self.bids))
        object.__setattr__(self, "asks", tuple(self.asks))
        # Bids must be sorted descending, asks ascending.
        for i in range(1, len(self.bids)):
            if self.bids[i - 1].price < self.bids[i].price:
                raise ValueError("OrderBookSnapshot.bids must be sorted descending by price")
        for i in range(1, len(self.asks)):
            if self.asks[i - 1].price > self.asks[i].price:
                raise ValueError("OrderBookSnapshot.asks must be sorted ascending by price")

    def to_dict(self) -> dict:
        return _dump(self)


# ---------------------------------------------------------------------------
# Trading
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Signal:
    """Strategy-emitted intent, prior to risk and routing."""

    strategy_id: str
    instrument_id: str
    side: Side
    strength: float = 1.0
    target_quantity: Optional[Decimal] = None
    target_price: Optional[Decimal] = None
    ts: datetime = field(default_factory=_utcnow)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.strategy_id:
            raise ValueError("Signal.strategy_id must be non-empty")
        if not self.instrument_id:
            raise ValueError("Signal.instrument_id must be non-empty")
        if not (-1.0 <= self.strength <= 1.0):
            raise ValueError("Signal.strength must be in [-1.0, 1.0]")
        object.__setattr__(self, "ts", _ensure_aware(self.ts))
        if self.target_quantity is not None:
            object.__setattr__(self, "target_quantity", _normalize_amount(self.target_quantity))
        if self.target_price is not None:
            object.__setattr__(self, "target_price", _normalize_amount(self.target_price))

    def to_dict(self) -> dict:
        return _dump(self)


@dataclass(frozen=True, slots=True)
class Order:
    """An order request as accepted by the execution engine.

    ``client_order_id`` is generated by the platform (idempotency key).
    ``venue_order_id`` is populated by the broker gateway after submission.
    """

    client_order_id: str
    instrument_id: str
    side: Side
    quantity: Decimal
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    time_in_force: TimeInForce = TimeInForce.DAY
    status: OrderStatus = OrderStatus.PENDING
    account_id: Optional[str] = None
    strategy_id: Optional[str] = None
    venue_order_id: Optional[str] = None
    submitted_at: Optional[datetime] = None
    filled_quantity: Decimal = Decimal("0")
    avg_fill_price: Optional[Decimal] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.client_order_id:
            raise ValueError("Order.client_order_id must be non-empty")
        if not self.instrument_id:
            raise ValueError("Order.instrument_id must be non-empty")
        object.__setattr__(self, "quantity", _normalize_amount(self.quantity))
        if self.quantity <= 0:
            raise ValueError("Order.quantity must be positive")
        object.__setattr__(self, "filled_quantity", _normalize_amount(self.filled_quantity))
        if self.filled_quantity < 0:
            raise ValueError("Order.filled_quantity must be non-negative")
        if self.filled_quantity > self.quantity:
            raise ValueError("Order.filled_quantity cannot exceed quantity")
        if self.limit_price is not None:
            object.__setattr__(self, "limit_price", _normalize_amount(self.limit_price))
        if self.stop_price is not None:
            object.__setattr__(self, "stop_price", _normalize_amount(self.stop_price))
        if self.avg_fill_price is not None:
            object.__setattr__(self, "avg_fill_price", _normalize_amount(self.avg_fill_price))
        if self.order_type in (OrderType.LIMIT, OrderType.STOP_LIMIT) and self.limit_price is None:
            raise ValueError(f"Order.limit_price required for {self.order_type.value}")
        if self.order_type in (OrderType.STOP, OrderType.STOP_LIMIT) and self.stop_price is None:
            raise ValueError(f"Order.stop_price required for {self.order_type.value}")
        if self.submitted_at is not None:
            object.__setattr__(self, "submitted_at", _ensure_aware(self.submitted_at))

    @property
    def remaining_quantity(self) -> Decimal:
        return self.quantity - self.filled_quantity

    @property
    def is_active(self) -> bool:
        return self.status in (
            OrderStatus.PENDING,
            OrderStatus.SUBMITTED,
            OrderStatus.PARTIALLY_FILLED,
        )

    def to_dict(self) -> dict:
        return _dump(self)


@dataclass(frozen=True, slots=True)
class Fill:
    """A single execution against an order."""

    fill_id: str
    client_order_id: str
    instrument_id: str
    side: Side
    quantity: Decimal
    price: Decimal
    ts: datetime
    commission: Decimal = Decimal("0")
    venue: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.fill_id:
            raise ValueError("Fill.fill_id must be non-empty")
        if not self.client_order_id:
            raise ValueError("Fill.client_order_id must be non-empty")
        object.__setattr__(self, "ts", _ensure_aware(self.ts))
        object.__setattr__(self, "quantity", _normalize_amount(self.quantity))
        object.__setattr__(self, "price", _normalize_amount(self.price))
        object.__setattr__(self, "commission", _normalize_amount(self.commission))
        if self.quantity <= 0:
            raise ValueError("Fill.quantity must be positive")
        if self.price < 0:
            raise ValueError("Fill.price must be non-negative")
        if self.commission < 0:
            raise ValueError("Fill.commission must be non-negative")

    def to_dict(self) -> dict:
        return _dump(self)


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Position:
    """Net position for one instrument inside one account."""

    account_id: str
    instrument_id: str
    quantity: Decimal
    avg_cost: Decimal
    ts: datetime = field(default_factory=_utcnow)
    realized_pnl: Decimal = Decimal("0")
    unrealized_pnl: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        if not self.account_id:
            raise ValueError("Position.account_id must be non-empty")
        if not self.instrument_id:
            raise ValueError("Position.instrument_id must be non-empty")
        object.__setattr__(self, "ts", _ensure_aware(self.ts))
        object.__setattr__(self, "quantity", _normalize_amount(self.quantity))
        object.__setattr__(self, "avg_cost", _normalize_amount(self.avg_cost))
        object.__setattr__(self, "realized_pnl", _normalize_amount(self.realized_pnl))
        object.__setattr__(self, "unrealized_pnl", _normalize_amount(self.unrealized_pnl))
        if self.avg_cost < 0:
            raise ValueError("Position.avg_cost must be non-negative")

    def to_dict(self) -> dict:
        return _dump(self)


@dataclass(frozen=True, slots=True)
class AccountSnapshot:
    """Cash + buying-power view of one account at one instant."""

    account_id: str
    ts: datetime
    cash: Decimal
    equity: Decimal
    buying_power: Decimal
    currency: str = "CNY"
    margin_used: Decimal = Decimal("0")
    positions: Tuple[Position, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.account_id:
            raise ValueError("AccountSnapshot.account_id must be non-empty")
        object.__setattr__(self, "ts", _ensure_aware(self.ts))
        for fld in ("cash", "equity", "buying_power", "margin_used"):
            object.__setattr__(self, fld, _normalize_amount(getattr(self, fld)))
        if self.equity < 0:
            raise ValueError("AccountSnapshot.equity must be non-negative")
        if self.buying_power < 0:
            raise ValueError("AccountSnapshot.buying_power must be non-negative")
        if self.margin_used < 0:
            raise ValueError("AccountSnapshot.margin_used must be non-negative")
        object.__setattr__(self, "positions", tuple(self.positions))

    def to_dict(self) -> dict:
        return _dump(self)


# ---------------------------------------------------------------------------
# Risk / admission
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RiskCheckResult:
    """Outcome of a pre-trade or post-trade risk evaluation."""

    decision: RiskDecision
    rule_id: str
    reason: str = ""
    ts: datetime = field(default_factory=_utcnow)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.rule_id:
            raise ValueError("RiskCheckResult.rule_id must be non-empty")
        object.__setattr__(self, "ts", _ensure_aware(self.ts))

    @property
    def approved(self) -> bool:
        return self.decision is RiskDecision.APPROVED

    def to_dict(self) -> dict:
        return _dump(self)


# ---------------------------------------------------------------------------
# Backtest / report
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BacktestResult:
    """Top-level summary returned by ``BacktestEngine``."""

    strategy_id: str
    start: datetime
    end: datetime
    initial_capital: Decimal
    final_equity: Decimal
    metrics: Mapping[str, Any] = field(default_factory=dict)
    artifacts: Mapping[str, str] = field(default_factory=dict)
    contract_version: str = ""

    def __post_init__(self) -> None:
        if not self.strategy_id:
            raise ValueError("BacktestResult.strategy_id must be non-empty")
        object.__setattr__(self, "start", _ensure_aware(self.start))
        object.__setattr__(self, "end", _ensure_aware(self.end))
        if self.end < self.start:
            raise ValueError("BacktestResult.end must be >= start")
        object.__setattr__(self, "initial_capital", _normalize_amount(self.initial_capital))
        object.__setattr__(self, "final_equity", _normalize_amount(self.final_equity))
        if self.initial_capital <= 0:
            raise ValueError("BacktestResult.initial_capital must be positive")
        if self.final_equity < 0:
            raise ValueError("BacktestResult.final_equity must be non-negative")

    @property
    def total_return(self) -> Decimal:
        return (self.final_equity - self.initial_capital) / self.initial_capital

    def to_dict(self) -> dict:
        return _dump(self)


__all__ = [
    # enums
    "AssetClass",
    "Side",
    "OrderType",
    "OrderStatus",
    "OrderStatusEnum",
    "TimeInForce",
    "RiskDecision",
    # helpers
    "normalize_order_status",
    "is_active_order_status",
    "is_terminal_order_status",
    # DTOs
    "Instrument",
    "Bar",
    "Tick",
    "BookLevel",
    "OrderBookSnapshot",
    "Signal",
    "Order",
    "Fill",
    "Position",
    "AccountSnapshot",
    "RiskCheckResult",
    "BacktestResult",
]
