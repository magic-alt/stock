"""Observability-plane ports: metrics, tracing, audit log."""
from __future__ import annotations

from typing import Any, Mapping, Optional, Protocol, runtime_checkable


@runtime_checkable
class MetricsPort(Protocol):
    """StatsD/Prometheus-style metric sink.

    Implementations MAY buffer or batch. ``tags`` are key/value labels.
    """

    def incr(self, name: str, value: float = 1.0, *, tags: Optional[Mapping[str, str]] = None) -> None:
        ...

    def gauge(self, name: str, value: float, *, tags: Optional[Mapping[str, str]] = None) -> None:
        ...

    def timing(self, name: str, ms: float, *, tags: Optional[Mapping[str, str]] = None) -> None:
        ...


@runtime_checkable
class TracerPort(Protocol):
    """OpenTelemetry-style span tracer.

    ``start_span`` MUST return a context manager that closes the span on exit.
    The exact type is left to the adapter — only the context-manager protocol
    is required.
    """

    def start_span(
        self,
        name: str,
        *,
        attributes: Optional[Mapping[str, Any]] = None,
    ) -> Any:
        ...


@runtime_checkable
class AuditPort(Protocol):
    """Append-only hash-chained audit log (V5 ``audit_log.py``).

    Implementations MUST produce a tamper-evident chain: each record's
    ``prev_hash`` MUST be the SHA-256 of the previous record's canonical
    serialisation. The verification side lives in
    ``scripts/audit_integrity_check.py``.
    """

    def append(self, actor: str, action: str, payload: Mapping[str, Any]) -> str:
        """Return the new record's hash."""

    def head(self) -> Optional[str]:
        """Return the latest record's hash, or ``None`` if the log is empty."""


__all__ = ["AuditPort", "MetricsPort", "TracerPort"]
