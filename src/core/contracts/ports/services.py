"""Service-plane ports: scheduler, vault, ML adapter, report renderer."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Mapping, Optional, Protocol, Sequence, runtime_checkable


@runtime_checkable
class SchedulerPort(Protocol):
    """Cron / interval scheduler used by engines and admission workflows."""

    def schedule_cron(self, expr: str, callback: Callable[[], None], *, job_id: Optional[str] = None) -> str:
        """Return the registered job id."""

    def schedule_at(self, when: datetime, callback: Callable[[], None], *, job_id: Optional[str] = None) -> str:
        ...

    def cancel(self, job_id: str) -> bool:
        ...

    def list_jobs(self) -> Sequence[str]:
        ...


@runtime_checkable
class VaultPort(Protocol):
    """Secrets store for API tokens and broker credentials.

    Implementations MUST NOT log secret values. Reads MUST be audited
    via the :class:`AuditPort` when one is configured.
    """

    def get_secret(self, name: str) -> Optional[str]:
        ...

    def set_secret(self, name: str, value: str) -> None:
        ...

    def delete_secret(self, name: str) -> bool:
        ...

    def list_secrets(self) -> Sequence[str]:
        """Return secret NAMES only (never values)."""


@runtime_checkable
class MLAdapterPort(Protocol):
    """ML inference adapter.

    The adapter abstracts framework choice (Qlib, FinRL, scikit-learn,
    PyTorch). Strategies depend only on this port; framework-specific
    plumbing lives in the adapter.
    """

    @property
    def model_id(self) -> str:
        ...

    def predict(self, features: Mapping[str, Any]) -> float:
        ...

    def batch_predict(self, batch: Sequence[Mapping[str, Any]]) -> Sequence[float]:
        ...


@runtime_checkable
class ReportPort(Protocol):
    """Renders a backtest / live-trading report from a result payload.

    Output format is implementation-defined (HTML, PDF, Jupyter notebook).
    The contract is purely: take a structured payload and produce a path
    to the rendered artefact.
    """

    @property
    def format(self) -> str:
        """Stable format token (``html``, ``pdf``, ``ipynb``, ...)."""

    def render(self, payload: Mapping[str, Any], output_dir: str) -> str:
        """Return path to the rendered file."""


__all__ = ["MLAdapterPort", "ReportPort", "SchedulerPort", "VaultPort"]
