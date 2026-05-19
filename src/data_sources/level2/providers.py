from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Protocol

from src.core.events import Event, EventType
from src.data_sources.level2.models import Level2Snapshot, OrderBookLevel, TradeTick


class Level2Unavailable(RuntimeError):
    """Raised when a configured Level2 provider cannot access its SDK/service."""


class Level2DataProvider(Protocol):
    provider_name: str

    def subscribe(self, symbols: Iterable[str]) -> None:
        ...

    def get_snapshot(self, symbol: str) -> Level2Snapshot:
        ...

    def parse_snapshot(self, payload: Dict[str, Any]) -> Level2Snapshot:
        ...


class StubLevel2Provider:
    """Deterministic Level2 provider for tests, demos, and offline development."""

    provider_name = "stub"

    def __init__(self, snapshots: Optional[Dict[str, Dict[str, Any]]] = None) -> None:
        self._payloads = dict(snapshots or {})
        self._subscriptions: set[str] = set()

    def subscribe(self, symbols: Iterable[str]) -> None:
        self._subscriptions.update(str(symbol) for symbol in symbols)

    def get_snapshot(self, symbol: str) -> Level2Snapshot:
        if symbol not in self._payloads:
            raise Level2Unavailable(f"No Level2 snapshot configured for {symbol}")
        return self.parse_snapshot(self._payloads[symbol])

    def parse_snapshot(self, payload: Dict[str, Any]) -> Level2Snapshot:
        symbol = str(payload.get("symbol", "")).strip()
        timestamp = _parse_timestamp(payload.get("timestamp"))
        bids = [_parse_level(item) for item in payload.get("bids", [])]
        asks = [_parse_level(item) for item in payload.get("asks", [])]
        trades = [_parse_trade(symbol, item) for item in payload.get("trades", [])]
        return Level2Snapshot(
            symbol=symbol,
            timestamp=timestamp,
            bids=bids,
            asks=asks,
            last_price=_optional_float(payload.get("last_price")),
            total_volume=_optional_float(payload.get("total_volume")),
            trades=trades,
            source=str(payload.get("source", self.provider_name)),
        )


class _SdkBackedLevel2Provider(StubLevel2Provider):
    provider_name = "sdk"

    def __init__(self, sdk: Any = None, snapshots: Optional[Dict[str, Dict[str, Any]]] = None) -> None:
        super().__init__(snapshots=snapshots)
        self.sdk = sdk

    def get_snapshot(self, symbol: str) -> Level2Snapshot:
        if symbol in self._payloads:
            return super().get_snapshot(symbol)
        if self.sdk is None:
            raise Level2Unavailable(f"{self.provider_name} Level2 SDK is not configured")
        getter = getattr(self.sdk, "get_level2_snapshot", None)
        if not callable(getter):
            raise Level2Unavailable(f"{self.provider_name} SDK does not expose get_level2_snapshot")
        return self.parse_snapshot(getter(symbol))


class XtpLevel2Provider(_SdkBackedLevel2Provider):
    provider_name = "xtp"


class HundsunLevel2Provider(_SdkBackedLevel2Provider):
    provider_name = "hundsun"


class QmtLevel2Provider(_SdkBackedLevel2Provider):
    provider_name = "qmt"


_PROVIDER_TYPES = {
    "stub": StubLevel2Provider,
    "mock": StubLevel2Provider,
    "xtp": XtpLevel2Provider,
    "hundsun": HundsunLevel2Provider,
    "uft": HundsunLevel2Provider,
    "qmt": QmtLevel2Provider,
    "xtquant": QmtLevel2Provider,
}


def create_level2_provider(name: str = "stub", **kwargs: Any) -> Level2DataProvider:
    provider_type = _PROVIDER_TYPES.get(name.strip().lower())
    if provider_type is None:
        available = ", ".join(sorted(_PROVIDER_TYPES))
        raise ValueError(f"Unsupported Level2 provider: {name}. Available: {available}")
    return provider_type(**kwargs)


def publish_level2_snapshot(event_engine: Any, snapshot: Level2Snapshot) -> None:
    event_engine.put(Event(EventType.LEVEL2_SNAPSHOT, snapshot.to_dict()))
    for trade in snapshot.trades:
        event_engine.put(Event(EventType.LEVEL2_TRADE, trade.to_dict()))


def _parse_level(item: Any) -> OrderBookLevel:
    if isinstance(item, dict):
        return OrderBookLevel(price=float(item["price"]), volume=float(item["volume"]))
    price, volume = item[:2]
    return OrderBookLevel(price=float(price), volume=float(volume))


def _parse_trade(symbol: str, item: Any) -> TradeTick:
    if isinstance(item, dict):
        return TradeTick(
            symbol=str(item.get("symbol") or symbol),
            price=float(item["price"]),
            volume=float(item["volume"]),
            side=str(item.get("side", "unknown")),
            timestamp=_parse_timestamp(item.get("timestamp")),
            trade_id=str(item.get("trade_id", "")),
        )
    price, volume, *rest = item
    side = str(rest[0]) if rest else "unknown"
    return TradeTick(symbol=symbol, price=float(price), volume=float(volume), side=side)


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if isinstance(value, str) and value:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def _optional_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    return float(value)
