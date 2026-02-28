"""
Distributed backtest runner with pluggable backends.

Supports:
- LocalProcessPool (default): ProcessPoolExecutor
- Ray: Optional ray.remote integration
- Dask: Optional dask.distributed integration
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed, Future
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Protocol

from src.platform.backtest_task import run_backtest_job


# ---------------------------------------------------------------------------
# Backend Protocol
# ---------------------------------------------------------------------------


class DistributedBackend(Protocol):
    """Protocol for distributed execution backends."""

    def submit(self, func: Callable, payload: Dict[str, Any]) -> str:
        """Submit a task. Returns a task identifier."""
        ...

    def collect_results(self) -> List[Dict[str, Any]]:
        """Block until all submitted tasks complete. Returns list of results."""
        ...

    def shutdown(self) -> None:
        """Release resources."""
        ...


# ---------------------------------------------------------------------------
# Local ProcessPool Backend
# ---------------------------------------------------------------------------


class LocalProcessPoolBackend:
    """Default backend using ProcessPoolExecutor."""

    def __init__(self, max_workers: int = 4) -> None:
        self.max_workers = max_workers
        self._executor = ProcessPoolExecutor(max_workers=max_workers)
        self._futures: List[Future] = []

    def submit(self, func: Callable, payload: Dict[str, Any]) -> str:
        future = self._executor.submit(func, payload)
        self._futures.append(future)
        return str(len(self._futures) - 1)

    def collect_results(self) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for future in as_completed(self._futures):
            try:
                results.append(future.result())
            except Exception as exc:
                results.append({"error": str(exc), "status": "failed"})
        self._futures.clear()
        return results

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False)


# ---------------------------------------------------------------------------
# Ray Backend (optional)
# ---------------------------------------------------------------------------


class RayBackend:
    """Ray-based distributed backend. Requires `ray` package."""

    def __init__(self, **ray_init_kwargs: Any) -> None:
        import ray as _ray
        self._ray = _ray
        if not _ray.is_initialized():
            _ray.init(**ray_init_kwargs)
        self._refs: List[Any] = []
        self._remote_fn: Optional[Any] = None

    def submit(self, func: Callable, payload: Dict[str, Any]) -> str:
        if self._remote_fn is None:
            self._remote_fn = self._ray.remote(func)
        ref = self._remote_fn.remote(payload)
        self._refs.append(ref)
        return str(len(self._refs) - 1)

    def collect_results(self) -> List[Dict[str, Any]]:
        results = self._ray.get(self._refs)
        self._refs.clear()
        return results

    def shutdown(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Dask Backend (optional)
# ---------------------------------------------------------------------------


class DaskBackend:
    """Dask-based distributed backend. Requires `dask.distributed`."""

    def __init__(self, client: Optional[Any] = None, **kwargs: Any) -> None:
        if client is not None:
            self._client = client
        else:
            from dask.distributed import Client
            self._client = Client(**kwargs)
        self._futures: List[Any] = []

    def submit(self, func: Callable, payload: Dict[str, Any]) -> str:
        future = self._client.submit(func, payload)
        self._futures.append(future)
        return str(len(self._futures) - 1)

    def collect_results(self) -> List[Dict[str, Any]]:
        results = self._client.gather(self._futures)
        self._futures.clear()
        return results

    def shutdown(self) -> None:
        pass


# ---------------------------------------------------------------------------
# DistributedRunner
# ---------------------------------------------------------------------------


class DistributedRunner:
    """High-level runner that selects backend and manages execution."""

    def __init__(
        self,
        backend: str = "local",
        max_workers: int = 4,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        **backend_kwargs: Any,
    ) -> None:
        self.backend_name = backend
        self.progress_callback = progress_callback
        self._backend: DistributedBackend

        if backend == "ray":
            self._backend = RayBackend(**backend_kwargs)
        elif backend == "dask":
            self._backend = DaskBackend(**backend_kwargs)
        else:
            self._backend = LocalProcessPoolBackend(max_workers=max_workers)

    def run(
        self,
        func: Callable[[Dict[str, Any]], Dict[str, Any]],
        payloads: Iterable[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        payload_list = list(payloads)
        total = len(payload_list)

        for p in payload_list:
            self._backend.submit(func, p)

        if self.progress_callback:
            self.progress_callback(0, total)

        results = self._backend.collect_results()

        if self.progress_callback:
            self.progress_callback(total, total)

        return results

    def shutdown(self) -> None:
        self._backend.shutdown()


# ---------------------------------------------------------------------------
# Legacy API (backward compatible)
# ---------------------------------------------------------------------------


def _run_job(payload: Dict[str, Any]) -> Dict[str, Any]:
    return run_backtest_job(payload)


def run_distributed_backtests(
    payloads: Iterable[Dict[str, Any]],
    *,
    max_workers: int = 4,
    backend: str = "local",
) -> List[Dict[str, Any]]:
    """Run backtest payloads in parallel across selected backend."""
    runner = DistributedRunner(backend=backend, max_workers=max_workers)
    try:
        return runner.run(_run_job, list(payloads))
    finally:
        runner.shutdown()
