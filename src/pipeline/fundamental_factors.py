"""
Fundamental Factor Module

Provides fundamental analysis factors (PE, PB, ROE, Revenue Growth, Dividend Yield)
following the same Factor ABC pattern used in factor_engine.py.

Input DataFrames should contain financial columns (eps, bps, roe, revenue, dps).
Missing columns gracefully produce NaN output.
"""
from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
import logging

from src.pipeline.factor_engine import Factor, Pipeline, create_pipeline

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Fundamental Factors
# ---------------------------------------------------------------------------

class PERatio(Factor):
    """Price-to-Earnings ratio (close / eps)."""

    def __init__(self):
        super().__init__()

    def compute(self, data: pd.DataFrame) -> pd.Series:
        if "close" not in data.columns or "eps" not in data.columns:
            return pd.Series(np.nan, index=data.index, name="pe_ratio")
        eps = data["eps"].replace(0, np.nan)
        return (data["close"] / eps).rename("pe_ratio")


class PBRatio(Factor):
    """Price-to-Book ratio (close / bps)."""

    def __init__(self):
        super().__init__()

    def compute(self, data: pd.DataFrame) -> pd.Series:
        if "close" not in data.columns or "bps" not in data.columns:
            return pd.Series(np.nan, index=data.index, name="pb_ratio")
        bps = data["bps"].replace(0, np.nan)
        return (data["close"] / bps).rename("pb_ratio")


class ROE(Factor):
    """Return on Equity factor (pass-through from financial data)."""

    def __init__(self):
        super().__init__()

    def compute(self, data: pd.DataFrame) -> pd.Series:
        if "roe" not in data.columns:
            return pd.Series(np.nan, index=data.index, name="roe")
        return data["roe"].rename("roe")


class RevenueGrowth(Factor):
    """Year-over-year revenue growth rate.

    Computes (revenue / revenue.shift(periods)) - 1.
    Default period is 4 quarters (252 trading days approximation).
    """

    def __init__(self, period: int = 252):
        super().__init__(period=period)

    def compute(self, data: pd.DataFrame) -> pd.Series:
        if "revenue" not in data.columns:
            return pd.Series(np.nan, index=data.index, name="revenue_growth")
        period = self.params["period"]
        prev = data["revenue"].shift(period)
        prev = prev.replace(0, np.nan)
        return ((data["revenue"] / prev) - 1).rename("revenue_growth")


class DividendYield(Factor):
    """Dividend yield (dps / close)."""

    def __init__(self):
        super().__init__()

    def compute(self, data: pd.DataFrame) -> pd.Series:
        if "close" not in data.columns or "dps" not in data.columns:
            return pd.Series(np.nan, index=data.index, name="dividend_yield")
        close = data["close"].replace(0, np.nan)
        return (data["dps"] / close).rename("dividend_yield")


class EarningsYield(Factor):
    """Earnings yield (eps / close) — inverse of PE."""

    def __init__(self):
        super().__init__()

    def compute(self, data: pd.DataFrame) -> pd.Series:
        if "close" not in data.columns or "eps" not in data.columns:
            return pd.Series(np.nan, index=data.index, name="earnings_yield")
        close = data["close"].replace(0, np.nan)
        return (data["eps"] / close).rename("earnings_yield")


class DebtToEquity(Factor):
    """Debt-to-equity ratio (total_debt / total_equity)."""

    def __init__(self):
        super().__init__()

    def compute(self, data: pd.DataFrame) -> pd.Series:
        if "total_debt" not in data.columns or "total_equity" not in data.columns:
            return pd.Series(np.nan, index=data.index, name="debt_to_equity")
        eq = data["total_equity"].replace(0, np.nan)
        return (data["total_debt"] / eq).rename("debt_to_equity")


# ---------------------------------------------------------------------------
# Financial Data Provider (stub for external integration)
# ---------------------------------------------------------------------------

class FinancialDataProvider:
    """Stub for loading fundamental financial data.

    In production, subclass this and implement ``load()`` to pull data from
    a financial database (Wind, Choice, TuShare pro, etc.).
    """

    def load(
        self,
        symbols: List[str],
        start: str,
        end: str,
    ) -> Dict[str, pd.DataFrame]:
        """Load financial data for symbols.

        Returns:
            Mapping of symbol -> DataFrame with columns such as
            eps, bps, roe, revenue, dps, total_debt, total_equity.
        """
        logger.warning(
            "FinancialDataProvider.load() is a stub — returning empty data. "
            "Subclass FinancialDataProvider and implement load() for real data."
        )
        return {}


# ---------------------------------------------------------------------------
# Pipeline helpers
# ---------------------------------------------------------------------------

def fundamental_pipeline() -> Pipeline:
    """Create a standard fundamental factor pipeline."""
    return create_pipeline(
        ("pe_ratio", PERatio()),
        ("pb_ratio", PBRatio()),
        ("roe", ROE()),
        ("revenue_growth", RevenueGrowth()),
        ("dividend_yield", DividendYield()),
    )


def full_fundamental_pipeline() -> Pipeline:
    """Create a comprehensive fundamental factor pipeline."""
    return create_pipeline(
        ("pe_ratio", PERatio()),
        ("pb_ratio", PBRatio()),
        ("roe", ROE()),
        ("revenue_growth", RevenueGrowth()),
        ("dividend_yield", DividendYield()),
        ("earnings_yield", EarningsYield()),
        ("debt_to_equity", DebtToEquity()),
    )
