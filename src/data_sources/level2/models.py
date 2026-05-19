from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class OrderBookLevel:
    price: float
    volume: float

    def to_dict(self) -> Dict[str, float]:
        return {"price": self.price, "volume": self.volume}


@dataclass(frozen=True)
class TradeTick:
    symbol: str
    price: float
    volume: float
    side: str = "unknown"
    timestamp: datetime = field(default_factory=_utc_now)
    trade_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["timestamp"] = self.timestamp.isoformat()
        return payload


@dataclass(frozen=True)
class Level2Snapshot:
    symbol: str
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]
    timestamp: datetime = field(default_factory=_utc_now)
    last_price: Optional[float] = None
    total_volume: Optional[float] = None
    trades: List[TradeTick] = field(default_factory=list)
    source: str = ""

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("symbol is required")
        if not self.bids and not self.asks:
            raise ValueError("at least one bid or ask level is required")
        object.__setattr__(self, "bids", sorted(self.bids, key=lambda level: level.price, reverse=True)[:10])
        object.__setattr__(self, "asks", sorted(self.asks, key=lambda level: level.price)[:10])

    @property
    def best_bid(self) -> Optional[OrderBookLevel]:
        return self.bids[0] if self.bids else None

    @property
    def best_ask(self) -> Optional[OrderBookLevel]:
        return self.asks[0] if self.asks else None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "last_price": self.last_price,
            "total_volume": self.total_volume,
            "source": self.source,
            "bids": [level.to_dict() for level in self.bids],
            "asks": [level.to_dict() for level in self.asks],
            "trades": [trade.to_dict() for trade in self.trades],
        }
