"""Data-plane ports: historical providers, live feeds, persistent storage.

All ports are :class:`typing.Protocol` so adapters may opt into structural
conformance without inheriting from the SDK. Each method docstring is the
binding contract — adapter authors must respect the documented semantics
(idempotency, exception types, ordering) regardless of inheritance.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, AsyncIterator, Iterable, Optional, Protocol, Sequence, runtime_checkable

from ..dto import AccountSnapshot, Bar, Fill, Instrument, Order, OrderBookSnapshot, Position, Tick


@runtime_checkable
class DataProviderPort(Protocol):
    """Pull-style historical data source (CSV files, Tushare, AkShare, ...)."""

    def get_instrument(self, instrument_id: str) -> Optional[Instrument]:
        """Return the reference data for ``instrument_id`` or ``None``."""

    def get_bars(
        self,
        instrument_id: str,
        start: datetime,
        end: datetime,
        interval: str = "1d",
    ) -> Sequence[Bar]:
        """Return bars in ascending ``ts`` order, half-open ``[start, end)``."""

    def list_instruments(
        self,
        *,
        exchange: Optional[str] = None,
        asset_class: Optional[str] = None,
    ) -> Sequence[Instrument]:
        """List instruments, optionally filtered by exchange / asset class."""


@runtime_checkable
class RealtimeFeedPort(Protocol):
    """Push-style live market data adapter."""

    def subscribe(self, instrument_ids: Iterable[str]) -> None:
        """Idempotent. Implementations MUST deduplicate."""

    def unsubscribe(self, instrument_ids: Iterable[str]) -> None:
        ...

    async def stream_ticks(self) -> AsyncIterator[Tick]:
        """Yield ticks until the adapter is closed. Ordering: per-instrument
        non-decreasing ``ts``; cross-instrument ordering is not guaranteed.
        """
        ...

    async def stream_books(self) -> AsyncIterator[OrderBookSnapshot]:
        ...


@runtime_checkable
class StoragePort(Protocol):
    """Generic key/value object store used by engines and adapters.

    Implementations MAY back this with DuckDB, SQLite, Parquet on disk,
    S3, or an in-memory dict in tests. The contract is namespace-scoped
    so plugins cannot collide.
    """

    def put(self, namespace: str, key: str, value: Any) -> None:
        ...

    def get(self, namespace: str, key: str) -> Optional[Any]:
        ...

    def delete(self, namespace: str, key: str) -> bool:
        """Return ``True`` if a value existed and was removed."""

    def list_keys(self, namespace: str, prefix: str = "") -> Sequence[str]:
        ...


@runtime_checkable
class PortfolioReaderPort(Protocol):
    """Read-only view of broker-side state used by risk and reporting."""

    def get_account(self, account_id: str) -> Optional[AccountSnapshot]:
        ...

    def get_position(self, account_id: str, instrument_id: str) -> Optional[Position]:
        ...

    def list_open_orders(self, account_id: str) -> Sequence[Order]:
        ...

    def list_fills_since(self, account_id: str, since: datetime) -> Sequence[Fill]:
        ...


__all__ = [
    "DataProviderPort",
    "PortfolioReaderPort",
    "RealtimeFeedPort",
    "StoragePort",
]
