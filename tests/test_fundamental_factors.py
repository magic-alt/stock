"""Tests for fundamental factors and factor analysis modules."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

try:
    import scipy  # noqa: F401
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False

from src.pipeline.fundamental_factors import (
    PERatio,
    PBRatio,
    ROE,
    RevenueGrowth,
    DividendYield,
    EarningsYield,
    DebtToEquity,
    FinancialDataProvider,
    fundamental_pipeline,
    full_fundamental_pipeline,
)
from src.pipeline.factor_analysis import (
    compute_factor_correlation,
    find_redundant_factors,
    factor_ic_analysis,
    factor_summary,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def financial_data():
    """Sample DataFrame with financial columns."""
    np.random.seed(42)
    n = 100
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {
            "close": np.random.uniform(10, 100, n),
            "eps": np.random.uniform(0.5, 5.0, n),
            "bps": np.random.uniform(5, 50, n),
            "roe": np.random.uniform(0.05, 0.30, n),
            "revenue": np.cumsum(np.random.uniform(1, 10, n)),
            "dps": np.random.uniform(0.1, 2.0, n),
            "total_debt": np.random.uniform(100, 500, n),
            "total_equity": np.random.uniform(200, 800, n),
            "open": np.random.uniform(10, 100, n),
            "high": np.random.uniform(10, 100, n),
            "low": np.random.uniform(10, 100, n),
            "volume": np.random.uniform(1e6, 1e7, n),
        },
        index=idx,
    )


@pytest.fixture
def ohlcv_only():
    """DataFrame with OHLCV only — no financial columns."""
    np.random.seed(7)
    n = 50
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {
            "open": np.random.uniform(10, 100, n),
            "high": np.random.uniform(10, 100, n),
            "low": np.random.uniform(10, 100, n),
            "close": np.random.uniform(10, 100, n),
            "volume": np.random.uniform(1e6, 1e7, n),
        },
        index=idx,
    )


# ---------------------------------------------------------------------------
# Fundamental factor tests
# ---------------------------------------------------------------------------

class TestPERatio:
    def test_compute(self, financial_data):
        result = PERatio().compute(financial_data)
        assert len(result) == len(financial_data)
        assert result.notna().sum() > 0
        # PE = close / eps; spot-check first row
        expected = financial_data["close"].iloc[0] / financial_data["eps"].iloc[0]
        assert abs(result.iloc[0] - expected) < 1e-6

    def test_missing_column(self, ohlcv_only):
        result = PERatio().compute(ohlcv_only)
        assert result.isna().all()


class TestPBRatio:
    def test_compute(self, financial_data):
        result = PBRatio().compute(financial_data)
        assert result.notna().sum() > 0

    def test_missing_column(self, ohlcv_only):
        result = PBRatio().compute(ohlcv_only)
        assert result.isna().all()


class TestROE:
    def test_compute(self, financial_data):
        result = ROE().compute(financial_data)
        pd.testing.assert_series_equal(
            result, financial_data["roe"].rename("roe"), check_names=True
        )

    def test_missing_column(self, ohlcv_only):
        result = ROE().compute(ohlcv_only)
        assert result.isna().all()


class TestRevenueGrowth:
    def test_compute(self, financial_data):
        factor = RevenueGrowth(period=5)
        result = factor.compute(financial_data)
        assert len(result) == len(financial_data)
        # First 5 values should be NaN due to shift
        assert result.iloc[:5].isna().all()
        assert result.iloc[5:].notna().any()

    def test_missing_column(self, ohlcv_only):
        result = RevenueGrowth().compute(ohlcv_only)
        assert result.isna().all()


class TestDividendYield:
    def test_compute(self, financial_data):
        result = DividendYield().compute(financial_data)
        expected = financial_data["dps"].iloc[0] / financial_data["close"].iloc[0]
        assert abs(result.iloc[0] - expected) < 1e-6

    def test_missing_column(self, ohlcv_only):
        result = DividendYield().compute(ohlcv_only)
        assert result.isna().all()


class TestEarningsYield:
    def test_compute(self, financial_data):
        result = EarningsYield().compute(financial_data)
        expected = financial_data["eps"].iloc[0] / financial_data["close"].iloc[0]
        assert abs(result.iloc[0] - expected) < 1e-6


class TestDebtToEquity:
    def test_compute(self, financial_data):
        result = DebtToEquity().compute(financial_data)
        expected = (
            financial_data["total_debt"].iloc[0]
            / financial_data["total_equity"].iloc[0]
        )
        assert abs(result.iloc[0] - expected) < 1e-6

    def test_missing_column(self, ohlcv_only):
        result = DebtToEquity().compute(ohlcv_only)
        assert result.isna().all()


class TestFinancialDataProvider:
    def test_stub_returns_empty(self):
        provider = FinancialDataProvider()
        data = provider.load(["600519.SH"], "2024-01-01", "2024-12-31")
        assert data == {}


# ---------------------------------------------------------------------------
# Pipeline tests
# ---------------------------------------------------------------------------

class TestFundamentalPipeline:
    def test_pipeline_runs(self, financial_data):
        pipe = fundamental_pipeline()
        result = pipe.run({"STOCK": financial_data})
        assert "pe_ratio" in result.columns
        assert "roe" in result.columns
        assert len(result) == len(financial_data)

    def test_full_pipeline(self, financial_data):
        pipe = full_fundamental_pipeline()
        result = pipe.run({"STOCK": financial_data})
        assert "earnings_yield" in result.columns
        assert "debt_to_equity" in result.columns

    def test_pipeline_graceful_missing(self, ohlcv_only):
        pipe = fundamental_pipeline()
        result = pipe.run({"STOCK": ohlcv_only})
        # PE/PB/DividendYield should be NaN, ROE should be NaN
        assert result["pe_ratio"].isna().all()
        assert result["roe"].isna().all()


# ---------------------------------------------------------------------------
# Factor analysis tests
# ---------------------------------------------------------------------------

class TestComputeFactorCorrelation:
    def test_basic(self):
        df = pd.DataFrame(
            {"a": [1, 2, 3, 4, 5], "b": [2, 4, 6, 8, 10], "c": [5, 4, 3, 2, 1]}
        )
        corr = compute_factor_correlation(df)
        assert corr.shape == (3, 3)
        # a and b perfectly correlated
        assert abs(corr.loc["a", "b"] - 1.0) < 1e-6
        # a and c perfectly negatively correlated
        assert abs(corr.loc["a", "c"] - (-1.0)) < 1e-6

    def test_empty(self):
        result = compute_factor_correlation(pd.DataFrame())
        assert result.empty


class TestFindRedundantFactors:
    def test_detects_perfect_correlation(self):
        df = pd.DataFrame(
            {"a": [1, 2, 3, 4, 5], "b": [2, 4, 6, 8, 10], "c": [5, 4, 3, 2, 1]}
        )
        pairs = find_redundant_factors(df, threshold=0.85)
        names = {(p[0], p[1]) for p in pairs}
        # a-b (corr=1.0) and a-c (|corr|=1.0) should be detected
        assert len(pairs) >= 2

    def test_low_threshold(self):
        df = pd.DataFrame({"a": [1, 2, 3], "b": [1, 2, 3]})
        pairs = find_redundant_factors(df, threshold=0.99)
        assert len(pairs) == 1

    def test_empty(self):
        assert find_redundant_factors(pd.DataFrame()) == []


@pytest.mark.skipif(not _HAS_SCIPY, reason="scipy not installed")
class TestFactorICAnalysis:
    def test_known_ic(self):
        # Factor perfectly predicts returns
        factor_df = pd.DataFrame({"f1": [1, 2, 3, 4, 5]})
        fwd = pd.Series([0.1, 0.2, 0.3, 0.4, 0.5], index=factor_df.index)
        ic = factor_ic_analysis(factor_df, fwd, method="spearman")
        assert abs(ic["f1"] - 1.0) < 1e-6

    def test_no_signal(self):
        np.random.seed(0)
        factor_df = pd.DataFrame({"f1": np.random.randn(100)})
        fwd = pd.Series(np.random.randn(100), index=factor_df.index)
        ic = factor_ic_analysis(factor_df, fwd)
        # Random should be near zero (within ±0.3)
        assert abs(ic["f1"]) < 0.3

    def test_empty_inputs(self):
        assert factor_ic_analysis(pd.DataFrame(), pd.Series(dtype=float)).empty


class TestFactorSummary:
    def test_basic(self):
        df = pd.DataFrame({"a": [1, 2, np.nan, 4], "b": [10, 20, 30, 40]})
        summary = factor_summary(df)
        assert "skew" in summary.columns
        assert "missing_pct" in summary.columns
        assert summary.loc["a", "missing_pct"] == 25.0
        assert summary.loc["b", "missing_pct"] == 0.0
