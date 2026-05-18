"""Engine backend abstraction layer.

V3.3.0: introduces the :class:`EngineBackend` ABC so that
:class:`src.backtest.engine.BacktestEngine` can swap the underlying execution
engine between **backtrader** (default) and **zipline** without changing the
public ``run_strategy`` / ``grid_search`` APIs.

Concrete backends live in ``src.backtest.backends.*``:

- ``BacktraderBackend`` — wraps the long-standing ``_run_module`` logic.
- ``ZiplineBackend`` — runs a strategy through ``zipline-reloaded`` via an
  adapter layer (signal → orders) that reuses the same ``StrategyModule``
  definitions where possible.

Backends are looked up by name through :class:`EngineRegistry` so external
plugins can register new engines (e.g. ``vectorbt``) without modifying the
core package.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple

import pandas as pd

# Type alias to avoid importing the heavy StrategyModule dataclass eagerly.
StrategyModuleLike = Any


@dataclass
class BackendRunResult:
    """Return value from ``EngineBackend.run``.

    Mirrors the legacy ``(nav, metrics, cerebro)`` tuple but as a named struct
    so engines that have no cerebro (zipline) can place arbitrary debug
    payloads in ``extra``.
    """

    nav: pd.Series
    metrics: Dict[str, Any]
    extra: Optional[Any] = None


class EngineBackend(ABC):
    """Abstract execution backend for a single strategy run."""

    #: Stable identifier used by :class:`EngineRegistry`. Subclasses override.
    name: str = ""

    @abstractmethod
    def run(
        self,
        module: StrategyModuleLike,
        data_map: Dict[str, pd.DataFrame],
        params: Dict[str, Any],
        *,
        cash: float,
        commission: float,
        slippage: float,
        benchmark_nav: Optional[pd.Series],
        return_cerebro: bool = False,
    ) -> BackendRunResult:
        """Run a single backtest and return NAV + metrics."""
        raise NotImplementedError


class EngineRegistry:
    """Process-wide registry of available execution backends."""

    _backends: Dict[str, Callable[[], EngineBackend]] = {}

    @classmethod
    def register(cls, name: str, factory: Callable[[], EngineBackend]) -> None:
        cls._backends[name.lower()] = factory

    @classmethod
    def get(cls, name: str) -> EngineBackend:
        key = (name or "backtrader").lower()
        if key not in cls._backends:
            available = ", ".join(sorted(cls._backends)) or "<none>"
            raise KeyError(
                f"Unknown backtest engine '{name}'. Registered engines: {available}"
            )
        return cls._backends[key]()

    @classmethod
    def available(cls) -> Tuple[str, ...]:
        return tuple(sorted(cls._backends))


def _register_defaults() -> None:
    """Lazily register the built-in backends.

    Backtrader is always present (hard dependency). Zipline is optional and
    only registered if ``zipline-reloaded`` imports successfully — otherwise
    the registry exposes ``backtrader`` only and the CLI / GUI prompt the user
    to install the extra.
    """
    if "backtrader" not in EngineRegistry._backends:
        def _make_backtrader():
            from src.backtest.backends.backtrader_backend import BacktraderBackend
            return BacktraderBackend()
        EngineRegistry.register("backtrader", _make_backtrader)
        EngineRegistry.register("bt", _make_backtrader)

    if "zipline" not in EngineRegistry._backends:
        def _make_zipline():
            from src.backtest.backends.zipline_backend import ZiplineBackend
            return ZiplineBackend()
        EngineRegistry.register("zipline", _make_zipline)


_register_defaults()
