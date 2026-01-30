"""
Data/feature adapters for AI framework integration.
"""
from __future__ import annotations

from typing import Dict, Iterable, Optional

import numpy as np
import pandas as pd

from src.data_sources.trading_calendar import TradingCalendar, align_frame_to_calendar

DEFAULT_COLUMN_MAP: Dict[str, str] = {
    "date": "timestamp",
    "datetime": "timestamp",
    "time": "timestamp",
    "open": "open",
    "high": "high",
    "low": "low",
    "close": "close",
    "volume": "volume",
    "vol": "volume",
}


def normalize_ohlcv_frame(
    df: pd.DataFrame,
    *,
    timestamp_col: Optional[str] = None,
    column_map: Optional[Dict[str, str]] = None,
) -> pd.DataFrame:
    """Normalize OHLCV columns and index to the platform standard."""
    if df is None or df.empty:
        return df

    out = df.copy()
    col_map = {k.lower(): v for k, v in (column_map or DEFAULT_COLUMN_MAP).items()}
    new_cols = {}
    for col in out.columns:
        mapped = col_map.get(str(col).lower())
        if mapped:
            new_cols[col] = mapped
    if new_cols:
        out = out.rename(columns=new_cols)

    ts_col = timestamp_col
    if ts_col and ts_col in out.columns:
        out.index = pd.to_datetime(out[ts_col])
        out = out.drop(columns=[ts_col])
    elif "timestamp" in out.columns:
        out.index = pd.to_datetime(out["timestamp"])
        out = out.drop(columns=["timestamp"])
    else:
        if not isinstance(out.index, pd.DatetimeIndex):
            out.index = pd.to_datetime(out.index)

    for col in ("open", "high", "low", "close", "volume"):
        if col not in out.columns:
            out[col] = 0.0

    out = out.sort_index()
    for col in ("open", "high", "low", "close", "volume"):
        out[col] = pd.to_numeric(out[col], errors="coerce").astype(float)
    return out


def align_to_trading_calendar(
    df: pd.DataFrame,
    *,
    start: str,
    end: str,
    calendar: Optional[TradingCalendar] = None,
    mode: str = "fill",
) -> pd.DataFrame:
    """Align a normalized OHLCV frame to a trading calendar."""
    if df is None or df.empty or mode == "off":
        return df
    calendar = calendar or TradingCalendar()
    sessions = calendar.sessions(start=start, end=end)
    return align_frame_to_calendar(df, sessions, fill_suspensions=(mode == "fill"))


def build_feature_frame(
    df: pd.DataFrame,
    *,
    include_returns: bool = True,
    include_volatility: bool = True,
    window: int = 20,
) -> pd.DataFrame:
    """Create a minimal feature frame for AI strategies."""
    if df is None or df.empty:
        return df
    out = df.copy()
    if include_returns and "close" in out.columns:
        out["return_1d"] = out["close"].pct_change().fillna(0.0)
        out["log_return_1d"] = np.log(out["close"].replace(0, np.nan)).diff().fillna(0.0)
    if include_volatility and "return_1d" in out.columns:
        out[f"vol_{window}"] = out["return_1d"].rolling(window=window, min_periods=1).std().fillna(0.0)
    return out
