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
# Financial Data Provider
# ---------------------------------------------------------------------------

# Canonical column names that downstream factors expect.
FINANCIAL_COLUMNS: List[str] = [
    "eps", "bps", "roe", "revenue", "dps", "total_debt", "total_equity",
]


class FinancialDataProvider:
    """Abstract base for loading fundamental financial data.

    Concrete implementations (Tushare / Akshare / Wind / Choice) must override
    :meth:`load` and return one DataFrame per requested symbol containing the
    canonical columns declared in :data:`FINANCIAL_COLUMNS`. The DataFrame index
    should be a :class:`pandas.DatetimeIndex` (report or announcement dates).
    Missing columns are tolerated by downstream factors but should be reported
    via ``logger.warning``.
    """

    name: str = "abstract"

    def load(
        self,
        symbols: List[str],
        start: str,
        end: str,
    ) -> Dict[str, pd.DataFrame]:
        """Return ``{symbol: financial_dataframe}`` for ``symbols``.

        Args:
            symbols: List of canonical symbol codes (``600519.SH`` form).
            start: Inclusive start date (``YYYY-MM-DD``).
            end: Inclusive end date (``YYYY-MM-DD``).
        """
        raise NotImplementedError(
            "FinancialDataProvider.load() must be implemented by a subclass."
        )

    # ---- shared helpers ---------------------------------------------------

    @staticmethod
    def _empty_frame() -> pd.DataFrame:
        return pd.DataFrame(columns=FINANCIAL_COLUMNS)

    @staticmethod
    def _ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
        for col in FINANCIAL_COLUMNS:
            if col not in df.columns:
                df[col] = np.nan
        return df[FINANCIAL_COLUMNS].sort_index()

    @staticmethod
    def _filter_window(df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
        if df.empty:
            return df
        idx = pd.to_datetime(df.index, errors="coerce")
        df = df.assign(_d=idx).dropna(subset=["_d"]).set_index("_d")
        mask = (df.index >= pd.to_datetime(start)) & (df.index <= pd.to_datetime(end))
        return df.loc[mask]


class NullFinancialProvider(FinancialDataProvider):
    """Returns an empty DataFrame for every symbol.

    Used as a safe fallback when no fundamental data backend is configured or
    when an optional dependency (tushare/akshare) is unavailable.
    """

    name = "null"

    def load(self, symbols: List[str], start: str, end: str) -> Dict[str, pd.DataFrame]:
        logger.warning(
            "NullFinancialProvider in use — no fundamental data backend configured. "
            "Set get_financial_provider('tushare'|'akshare') to enable real data."
        )
        return {sym: self._empty_frame() for sym in symbols}


class TushareFinancialProvider(FinancialDataProvider):
    """Tushare Pro fundamental data provider.

    Requires ``tushare`` and a ``TUSHARE_TOKEN`` environment variable.
    Pulls ``fina_indicator`` (EPS/BPS/ROE), ``income`` (revenue), ``dividend`` (DPS),
    and ``balancesheet`` (total_liab/total_hldr_eqy_inc_min_int) per symbol.
    """

    name = "tushare"

    def __init__(self, token: Optional[str] = None):
        try:
            import tushare as ts  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dep
            raise ImportError(
                "tushare is not installed. Install with `pip install tushare` and set TUSHARE_TOKEN."
            ) from exc
        import os
        self._token = token or os.environ.get("TUSHARE_TOKEN", "")
        if not self._token:
            raise RuntimeError(
                "TUSHARE_TOKEN is not set. Provide it via env or constructor argument."
            )
        ts.set_token(self._token)
        self._api = ts.pro_api()

    @staticmethod
    def _to_ts_symbol(symbol: str) -> str:
        return symbol.replace("SHA", "SH").replace("SZA", "SZ")

    @staticmethod
    def _to_ts_date(date: str) -> str:
        return date.replace("-", "")

    def _fetch_one(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        ts_code = self._to_ts_symbol(symbol)
        start_ts = self._to_ts_date(start)
        end_ts = self._to_ts_date(end)
        frames: List[pd.DataFrame] = []

        try:
            ind = self._api.fina_indicator(ts_code=ts_code, start_date=start_ts, end_date=end_ts)
        except Exception as exc:  # pragma: no cover - network
            logger.warning("tushare fina_indicator failed for %s: %s", symbol, exc)
            ind = pd.DataFrame()
        if not ind.empty:
            ind = ind.rename(columns={"eps": "eps", "bps": "bps", "roe": "roe"})
            ind["date"] = pd.to_datetime(ind["end_date"], errors="coerce")
            frames.append(ind.set_index("date")[["eps", "bps", "roe"]])

        try:
            inc = self._api.income(ts_code=ts_code, start_date=start_ts, end_date=end_ts)
        except Exception as exc:  # pragma: no cover
            logger.warning("tushare income failed for %s: %s", symbol, exc)
            inc = pd.DataFrame()
        if not inc.empty:
            inc["date"] = pd.to_datetime(inc["end_date"], errors="coerce")
            frames.append(inc.set_index("date")[["revenue"]].rename(columns={"revenue": "revenue"}))

        try:
            bal = self._api.balancesheet(ts_code=ts_code, start_date=start_ts, end_date=end_ts)
        except Exception as exc:  # pragma: no cover
            logger.warning("tushare balancesheet failed for %s: %s", symbol, exc)
            bal = pd.DataFrame()
        if not bal.empty:
            bal["date"] = pd.to_datetime(bal["end_date"], errors="coerce")
            bal = bal.set_index("date")
            equity_col = "total_hldr_eqy_inc_min_int" if "total_hldr_eqy_inc_min_int" in bal.columns else "total_hldr_eqy_exc_min_int"
            bal = bal.rename(columns={"total_liab": "total_debt", equity_col: "total_equity"})
            keep = [c for c in ("total_debt", "total_equity") if c in bal.columns]
            if keep:
                frames.append(bal[keep])

        try:
            div = self._api.dividend(ts_code=ts_code, start_date=start_ts, end_date=end_ts)
        except Exception as exc:  # pragma: no cover
            logger.warning("tushare dividend failed for %s: %s", symbol, exc)
            div = pd.DataFrame()
        if not div.empty and "cash_div" in div.columns:
            div["date"] = pd.to_datetime(div.get("ann_date", div.get("end_date")), errors="coerce")
            frames.append(
                div.set_index("date")[["cash_div"]].rename(columns={"cash_div": "dps"})
            )

        if not frames:
            return self._empty_frame()
        merged = pd.concat(frames, axis=1)
        # Keep latest value when duplicate index rows exist for the same date.
        merged = merged[~merged.index.duplicated(keep="last")]
        merged = self._filter_window(merged, start, end)
        return self._ensure_columns(merged)

    def load(self, symbols: List[str], start: str, end: str) -> Dict[str, pd.DataFrame]:
        return {sym: self._fetch_one(sym, start, end) for sym in symbols}


class AkshareFinancialProvider(FinancialDataProvider):
    """Akshare fundamental data provider (no API key required).

    Uses ``stock_financial_analysis_indicator`` for per-report-date metrics.
    Akshare returns Chinese column names; we map a curated subset to the
    canonical fields. Missing fields remain NaN.
    """

    name = "akshare"

    _ZH_TO_CANON = {
        "摊薄每股收益(元)": "eps",
        "每股净资产_调整后(元)": "bps",
        "净资产收益率(%)": "roe",
        "主营业务收入(元)": "revenue",
        "每股股利(元)": "dps",
        "负债合计(元)": "total_debt",
        "股东权益合计(不含少数股东权益)(元)": "total_equity",
    }

    def __init__(self) -> None:
        try:
            import akshare as ak  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "akshare is not installed. Install with `pip install akshare`."
            ) from exc
        self._ak = ak

    @staticmethod
    def _to_ak_symbol(symbol: str) -> str:
        # 600519.SH -> 600519
        return symbol.split(".")[0]

    def _fetch_one(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        code = self._to_ak_symbol(symbol)
        try:
            df = self._ak.stock_financial_analysis_indicator(symbol=code)
        except Exception as exc:  # pragma: no cover - network
            logger.warning("akshare stock_financial_analysis_indicator failed for %s: %s", symbol, exc)
            return self._empty_frame()
        if df is None or df.empty:
            return self._empty_frame()
        df = df.rename(columns=self._ZH_TO_CANON)
        # The "日期" index from akshare is the report period.
        if "日期" in df.columns:
            df["_d"] = pd.to_datetime(df["日期"], errors="coerce")
            df = df.dropna(subset=["_d"]).set_index("_d")
        else:
            df.index = pd.to_datetime(df.index, errors="coerce")
        # Coerce numeric.
        for col in FINANCIAL_COLUMNS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df = self._filter_window(df, start, end)
        return self._ensure_columns(df)

    def load(self, symbols: List[str], start: str, end: str) -> Dict[str, pd.DataFrame]:
        return {sym: self._fetch_one(sym, start, end) for sym in symbols}


_FINANCIAL_PROVIDERS: Dict[str, type] = {
    "null": NullFinancialProvider,
    "none": NullFinancialProvider,
    "tushare": TushareFinancialProvider,
    "akshare": AkshareFinancialProvider,
}


def get_financial_provider(name: str = "null", **kwargs: Any) -> FinancialDataProvider:
    """Factory for fundamental data providers.

    Args:
        name: One of ``null``, ``tushare``, ``akshare``.
        **kwargs: Forwarded to the provider constructor (e.g. ``token=...``).

    Returns:
        A :class:`FinancialDataProvider` instance. If the requested provider
        cannot be constructed (optional dependency missing or auth error),
        a :class:`NullFinancialProvider` is returned and a warning is logged.
    """
    key = (name or "null").strip().lower()
    cls = _FINANCIAL_PROVIDERS.get(key)
    if cls is None:
        logger.warning(
            "Unknown financial provider %r — falling back to NullFinancialProvider.", name
        )
        return NullFinancialProvider()
    try:
        return cls(**kwargs)
    except Exception as exc:
        logger.warning(
            "Failed to construct %s financial provider: %s. Using NullFinancialProvider.",
            name, exc,
        )
        return NullFinancialProvider()


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
