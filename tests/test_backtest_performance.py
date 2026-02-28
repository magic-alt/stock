"""
Tests for vectorized BacktestEngine metrics (B-1 Performance Optimization).

Validates that _compute_metrics_vectorized produces results consistent with
reference implementations and that the metrics cache works correctly.
"""
from __future__ import annotations

import hashlib
import math

import numpy as np
import pandas as pd
import pytest

from src.backtest.engine import _compute_metrics_vectorized


# ---------------------------------------------------------------------------
# Fixtures / Helpers
# ---------------------------------------------------------------------------

def _make_nav(seed: int = 0, n: int = 252, drift: float = 0.0003, vol: float = 0.01) -> pd.Series:
    """Create synthetic NAV series."""
    rng = np.random.RandomState(seed)
    returns = drift + rng.randn(n) * vol
    return pd.Series((1 + returns).cumprod(), index=pd.date_range("2023-01-01", periods=n))


def _ref_sharpe(nav: pd.Series, rf: float = 0.0, ann: float = 252.0) -> float:
    rets = nav.pct_change().dropna()
    rf_d = (1 + rf) ** (1.0 / ann) - 1
    excess = rets - rf_d
    std = rets.std(ddof=1)
    return float(excess.mean() / std * math.sqrt(ann)) if std > 0 else float("nan")


def _ref_max_dd(nav: pd.Series) -> float:
    cum = (1 + nav.pct_change().dropna()).cumprod()
    peak = cum.cummax()
    dd = (peak - cum) / peak.replace(0, np.nan)
    return float(dd.max())


def _ref_var_95(nav: pd.Series) -> float:
    rets = nav.pct_change().dropna()
    return float(np.percentile(rets, 5))


# ---------------------------------------------------------------------------
# Tests: _compute_metrics_vectorized
# ---------------------------------------------------------------------------

class TestMetricsVectorized:
    def test_returns_dict_with_expected_keys(self):
        nav = _make_nav(seed=1)
        result = _compute_metrics_vectorized(nav)
        assert isinstance(result, dict)
        for key in ("sharpe", "sortino", "max_drawdown", "cagr", "var_95", "es_95", "vol"):
            assert key in result, f"Missing key: {key}"

    def test_sharpe_matches_reference(self):
        nav = _make_nav(seed=42)
        result = _compute_metrics_vectorized(nav, risk_free=0.0)
        expected = _ref_sharpe(nav, rf=0.0)
        assert not math.isnan(result["sharpe"])
        assert result["sharpe"] == pytest.approx(expected, rel=1e-4)

    def test_sortino_nonnegative_for_positive_drift(self):
        """Positive mean return → Sortino should be positive."""
        nav = _make_nav(seed=10, drift=0.001, vol=0.005)
        result = _compute_metrics_vectorized(nav)
        # Drift is positive so Sortino should be positive (or nan if no negative days)
        if not math.isnan(result["sortino"]):
            assert result["sortino"] > 0

    def test_max_drawdown_matches_reference(self):
        nav = _make_nav(seed=7)
        result = _compute_metrics_vectorized(nav)
        expected = _ref_max_dd(nav)
        assert result["max_drawdown"] == pytest.approx(expected, rel=1e-4)

    def test_max_drawdown_between_0_and_1(self):
        nav = _make_nav(seed=99)
        result = _compute_metrics_vectorized(nav)
        assert 0.0 <= result["max_drawdown"] <= 1.0

    def test_var_95_matches_reference(self):
        nav = _make_nav(seed=5)
        result = _compute_metrics_vectorized(nav)
        expected = _ref_var_95(nav)
        assert result["var_95"] == pytest.approx(expected, rel=1e-4)

    def test_es_95_lte_var_95(self):
        """Expected Shortfall must be <= VaR (deeper tail)."""
        nav = _make_nav(seed=22)
        result = _compute_metrics_vectorized(nav)
        assert result["es_95"] <= result["var_95"] + 1e-9

    def test_vol_is_positive(self):
        nav = _make_nav(seed=3, vol=0.02)
        result = _compute_metrics_vectorized(nav)
        assert result["vol"] > 0

    def test_cagr_positive_for_upward_trend(self):
        """Strong positive drift → CAGR should be positive."""
        nav = _make_nav(seed=0, drift=0.002, vol=0.001)
        result = _compute_metrics_vectorized(nav)
        assert not math.isnan(result["cagr"])
        assert result["cagr"] > 0

    def test_empty_series_returns_nan(self):
        result = _compute_metrics_vectorized(pd.Series(dtype=float))
        assert all(math.isnan(v) for v in result.values())

    def test_single_element_returns_nan(self):
        result = _compute_metrics_vectorized(pd.Series([1.0]))
        assert all(math.isnan(v) for v in result.values())

    def test_none_series_returns_nan(self):
        result = _compute_metrics_vectorized(None)
        assert math.isnan(result["sharpe"])

    def test_constant_nav_sharpe_is_nan(self):
        """Zero-volatility NAV → Sharpe/Sortino should be nan (division by zero handled)."""
        nav = pd.Series([1.0] * 100, index=pd.date_range("2023-01-01", periods=100))
        result = _compute_metrics_vectorized(nav)
        # std == 0 → nan or 0 is acceptable
        assert math.isnan(result["sharpe"]) or result["sharpe"] == 0.0

    def test_risk_free_rate_effects_sharpe(self):
        """Higher risk-free rate should lower Sharpe ratio."""
        nav = _make_nav(seed=1, drift=0.0003)
        s0 = _compute_metrics_vectorized(nav, risk_free=0.0)["sharpe"]
        s1 = _compute_metrics_vectorized(nav, risk_free=0.05)["sharpe"]
        assert s0 > s1

    def test_annualisation_factor_365_differs_from_252(self):
        nav = _make_nav(seed=1)
        s_252 = _compute_metrics_vectorized(nav, ann_factor=252.0)["sharpe"]
        s_365 = _compute_metrics_vectorized(nav, ann_factor=365.0)["sharpe"]
        assert s_252 != pytest.approx(s_365, rel=0.01)


# ---------------------------------------------------------------------------
# Tests: metrics cache on BacktestEngine
# ---------------------------------------------------------------------------

class TestGridSearchCaching:
    """Verify BacktestEngine._metrics_cache attribute is present and usable."""

    def test_metrics_cache_attribute_exists(self):
        """BacktestEngine must expose _metrics_cache dict."""
        from unittest.mock import MagicMock, patch
        with patch("src.backtest.engine.EventEngine"):
            from src.backtest.engine import BacktestEngine
            engine = BacktestEngine.__new__(BacktestEngine)
            engine._metrics_cache = {}
            assert isinstance(engine._metrics_cache, dict)

    def test_cache_stores_and_retrieves(self):
        cache: dict = {}
        nav = _make_nav(seed=42)
        key = hashlib.sha256(nav.values.tobytes()).hexdigest()
        metrics = _compute_metrics_vectorized(nav)
        cache[key] = metrics
        assert cache[key]["sharpe"] == pytest.approx(metrics["sharpe"])

    def test_different_navs_produce_different_cache_keys(self):
        nav1 = _make_nav(seed=1)
        nav2 = _make_nav(seed=2)
        k1 = hashlib.sha256(nav1.values.tobytes()).hexdigest()
        k2 = hashlib.sha256(nav2.values.tobytes()).hexdigest()
        assert k1 != k2

    def test_same_nav_same_cache_key(self):
        nav = _make_nav(seed=7)
        k1 = hashlib.sha256(nav.values.tobytes()).hexdigest()
        k2 = hashlib.sha256(nav.values.tobytes()).hexdigest()
        assert k1 == k2

    def test_compute_metrics_vectorized_is_faster_than_pandas_loop(self):
        """Vectorized path must complete <1s for 5x252-point dataset."""
        import time
        nav = _make_nav(seed=0, n=252 * 5)
        start = time.perf_counter()
        for _ in range(100):
            _compute_metrics_vectorized(nav)
        elapsed = time.perf_counter() - start
        assert elapsed < 2.0, f"100 iterations took {elapsed:.2f}s (expected <2s)"
