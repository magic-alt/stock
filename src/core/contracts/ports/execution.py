"""Execution-plane ports: broker gateways, order routing, fill/slippage models."""
from __future__ import annotations

from typing import Mapping, Optional, Protocol, Sequence, runtime_checkable

from ..dto import Bar, Fill, Order, OrderBookSnapshot, Side


@runtime_checkable
class BrokerGatewayPort(Protocol):
    """Adapter to a single broker / venue.

    Implementations MUST be idempotent on ``client_order_id``: submitting
    the same id twice MUST return the same logical order without creating
    a duplicate at the venue.
    """

    @property
    def venue(self) -> str:
        """Stable venue identifier (e.g. ``CTP``, ``IB``, ``OKX``)."""

    def submit(self, order: Order) -> Order:
        """Submit ``order``; return the order with ``status`` advanced and
        ``venue_order_id`` populated when applicable.
        """

    def cancel(self, client_order_id: str) -> bool:
        """Return ``True`` if the cancel request was accepted by the venue."""

    def query_order(self, client_order_id: str) -> Optional[Order]:
        ...


@runtime_checkable
class OrderRouterPort(Protocol):
    """Selects a :class:`BrokerGatewayPort` for an order.

    Routers may multiplex venues, split orders by size, or honour user-pinned
    routes. The router NEVER mutates the order; it only chooses a destination.
    """

    def route(self, order: Order, *, hints: Optional[Mapping[str, str]] = None) -> str:
        """Return the destination venue id."""

    def list_venues(self) -> Sequence[str]:
        ...


@runtime_checkable
class FillModelPort(Protocol):
    """Backtest-side execution simulator.

    Decides how a pending order interacts with the next bar / book snapshot.
    """

    def fill_against_bar(self, order: Order, bar: Bar) -> Sequence[Fill]:
        """Return zero or more fills produced by ``order`` against ``bar``."""

    def fill_against_book(self, order: Order, book: OrderBookSnapshot) -> Sequence[Fill]:
        ...


@runtime_checkable
class SlippageModelPort(Protocol):
    """Adjusts a theoretical fill price to model market impact / spread."""

    def adjust(self, side: Side, reference_price: float, quantity: float) -> float:
        """Return the effective fill price."""


__all__ = [
    "BrokerGatewayPort",
    "FillModelPort",
    "OrderRouterPort",
    "SlippageModelPort",
]
