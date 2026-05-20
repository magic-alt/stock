"""Messaging-plane port.

The default in-process implementation lives in ``src/core/message_bus.py``;
this Protocol exists so third-party plugins (Redis, ZMQ, Kafka) can declare
they speak the same surface without importing the concrete class.
"""
from __future__ import annotations

from typing import Any, Callable, Optional, Protocol, runtime_checkable


@runtime_checkable
class MessageBusPort(Protocol):
    """Publish/subscribe bus.

    Topic strings use dot-notation (``kernel.component.state``,
    ``market.tick.600519.XSHG``). Subscribers receive a ``Message``
    envelope; implementations MAY deliver synchronously (in-process) or
    asynchronously (network transports).
    """

    def publish(self, topic: str, payload: Any, *, source: Optional[str] = None) -> int:
        """Publish ``payload`` to ``topic``; return number of delivered subscribers."""

    def subscribe(self, topic: str, handler: Callable[..., Any]) -> str:
        """Return an opaque subscription id usable with :py:meth:`unsubscribe`."""

    def unsubscribe(self, subscription_id: str) -> bool:
        ...

    def close(self) -> None:
        ...


__all__ = ["MessageBusPort"]
