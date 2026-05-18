"""Backtrader engine backend.

V3.3.0: extracts the backtrader execution path behind the
:class:`EngineBackend` interface. The actual heavy lifting (cerebro setup,
analyzers, metrics aggregation) still lives in
``BacktestEngine._run_module`` — this backend delegates there so we don't
duplicate the ~500 lines of metric-collection logic during the initial
refactor. A future refactor can hoist that body into this module.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd

from src.backtest.engine_base import BackendRunResult, EngineBackend


class BacktraderBackend(EngineBackend):
    """Wraps the legacy ``BacktestEngine._run_module`` body."""

    name = "backtrader"

    def run(
        self,
        module,
        data_map: Dict[str, pd.DataFrame],
        params: Dict[str, Any],
        *,
        cash: float,
        commission: float,
        slippage: float,
        benchmark_nav: Optional[pd.Series],
        return_cerebro: bool = False,
    ) -> BackendRunResult:
        # Local import avoids a circular dependency: engine.py imports the
        # registry, which lazily resolves this class.
        from src.backtest.engine import BacktestEngine

        nav, metrics, cerebro = BacktestEngine._run_module(
            module,
            data_map,
            params,
            cash=cash,
            commission=commission,
            slippage=slippage,
            benchmark_nav=benchmark_nav,
            return_cerebro=return_cerebro,
        )
        return BackendRunResult(nav=nav, metrics=metrics, extra=cerebro)
