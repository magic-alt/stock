"""Strategy backtest contract tests.

These tests are designed as CI gates:
- every registered backtestable strategy must complete a minimum synthetic run
- alias mappings must resolve to registered strategies
- new strategies are included in the smoke suite by default
"""
from __future__ import annotations

import math
from typing import Dict

import numpy as np
import pandas as pd
import pytest

from src.backtest.engine import BacktestEngine
from src.backtest.strategy_modules import STRATEGY_REGISTRY
from src.strategies.backtrader_registry import BACKTRADER_STRATEGY_REGISTRY, STRATEGY_ALIASES


SMOKE_EXCLUDED_STRATEGIES = {"qlib_registry"}
SMOKE_STRATEGIES = sorted(set(STRATEGY_REGISTRY) - SMOKE_EXCLUDED_STRATEGIES)


@pytest.fixture(scope="module")
def synthetic_market() -> Dict[str, object]:
    """Create deterministic single-symbol and multi-symbol test data."""
    rng = np.random.default_rng(20260409)
    dates = pd.bdate_range("2023-01-02", periods=320)
    base = np.linspace(100.0, 140.0, len(dates))
    cycle = 4.0 * np.sin(np.linspace(0.0, 12.0 * math.pi, len(dates)))
    noise = rng.normal(0.0, 0.6, len(dates)).cumsum() * 0.08
    close_seed = base + cycle + noise

    def make_df(seed_shift: int, scale: float, drift: float) -> pd.DataFrame:
        local_rng = np.random.default_rng(500 + seed_shift)
        close = close_seed * scale + np.linspace(0.0, drift, len(dates))
        close = close + local_rng.normal(0.0, 0.5, len(dates)).cumsum() * 0.05
        open_ = close * (1 + local_rng.normal(0.0, 0.004, len(dates)))
        high = np.maximum(open_, close) * 1.012
        low = np.minimum(open_, close) * 0.988
        volume = local_rng.integers(120_000, 520_000, len(dates))
        return pd.DataFrame(
            {
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            },
            index=dates,
        )

    ml_dates = pd.bdate_range("2023-01-02", periods=160)
    ml_base = np.linspace(80.0, 110.0, len(ml_dates))
    ml_cycle = 2.5 * np.sin(np.linspace(0.0, 8.0 * math.pi, len(ml_dates)))
    ml_noise = rng.normal(0.0, 0.4, len(ml_dates)).cumsum() * 0.05
    ml_close_seed = ml_base + ml_cycle + ml_noise

    def make_ml_df(seed_shift: int) -> pd.DataFrame:
        local_rng = np.random.default_rng(800 + seed_shift)
        close = ml_close_seed + local_rng.normal(0.0, 0.35, len(ml_dates)).cumsum() * 0.03
        open_ = close * (1 + local_rng.normal(0.0, 0.003, len(ml_dates)))
        high = np.maximum(open_, close) * 1.01
        low = np.minimum(open_, close) * 0.99
        volume = local_rng.integers(100_000, 400_000, len(ml_dates))
        return pd.DataFrame(
            {
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            },
            index=ml_dates,
        )

    return {
        "single": {"000001.SZ": make_df(seed_shift=0, scale=1.0, drift=0.0)},
        "multi": {
            "000001.SZ": make_df(seed_shift=0, scale=1.0, drift=0.0),
            "000300.SH": make_df(seed_shift=1, scale=0.82, drift=8.0),
            "399006.SZ": make_df(seed_shift=2, scale=1.18, drift=-4.0),
        },
        "benchmark": pd.Series(np.linspace(1.0, 1.12, len(dates)), index=dates),
        "ml_single": {"000001.SZ": make_ml_df(seed_shift=0)},
        "ml_benchmark": pd.Series(np.linspace(1.0, 1.08, len(ml_dates)), index=ml_dates),
    }


def test_smoke_suite_only_excludes_external_dependency_strategies() -> None:
    """Every strategy must be smoke-tested unless it has an explicit reason not to be."""
    assert set(STRATEGY_REGISTRY) - set(SMOKE_STRATEGIES) == SMOKE_EXCLUDED_STRATEGIES


def test_strategy_aliases_only_point_to_registered_backtests() -> None:
    """Alias resolution must not advertise strategies that the engine cannot run."""
    dangling_aliases = {
        alias: actual
        for alias, actual in STRATEGY_ALIASES.items()
        if actual not in BACKTRADER_STRATEGY_REGISTRY
    }
    assert dangling_aliases == {}


def _build_smoke_params(strategy_name: str, module) -> Dict[str, object]:
    """Use lighter but valid parameters for expensive ML smoke tests."""
    params: Dict[str, object] = dict(module.defaults)
    if strategy_name.startswith("ml_"):
        params.update(
            {
                "min_train": 60,
                "label_h": 1,
                "cooldown_bars": 1,
                "min_holding_bars": 1,
            }
        )
    return params


@pytest.mark.parametrize("strategy_name", SMOKE_STRATEGIES)
def test_registered_strategy_completes_minimum_backtest(
    strategy_name: str,
    synthetic_market: Dict[str, object],
) -> None:
    """Each strategy must finish a deterministic synthetic run without runtime errors."""
    module = STRATEGY_REGISTRY[strategy_name]
    if strategy_name.startswith("ml_"):
        data_map = synthetic_market["ml_single"]
        benchmark = synthetic_market["ml_benchmark"]
    else:
        data_map = synthetic_market["multi"] if module.multi_symbol else synthetic_market["single"]
        benchmark = synthetic_market["benchmark"]

    _, metrics, _ = BacktestEngine()._run_module(
        module,
        data_map,  # type: ignore[arg-type]
        module.coerce(_build_smoke_params(strategy_name, module)),
        cash=100_000,
        commission=0.0001,
        slippage=0.0001,
        benchmark_nav=benchmark,  # type: ignore[arg-type]
    )

    assert metrics.get("error") in (None, "")
    assert math.isfinite(float(metrics["final_value"]))
    assert float(metrics["final_value"]) > 0.0
    assert "cum_return" in metrics
    assert "mdd" in metrics
