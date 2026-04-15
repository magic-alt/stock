"""
Trading calendar utilities for backtest alignment and suspension handling.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import ClassVar, Iterable, Optional

import pandas as pd

try:  # pragma: no cover - exercised through public behavior
    import exchange_calendars as xcals
except ImportError:  # pragma: no cover - graceful fallback when optional dep is missing
    xcals = None


@lru_cache(maxsize=8)
def _get_exchange_calendar(exchange: str):
    if xcals is None:
        raise RuntimeError("exchange_calendars is not installed")
    return xcals.get_calendar(exchange)


@dataclass(frozen=True)
class TradingCalendar:
    """Trading calendar with optional exchange sessions and holiday exclusions."""

    SOURCE_EXCHANGE_MAP: ClassVar[dict[str, Optional[str]]] = {
        "akshare": "XSHG",
        "qlib": "XSHG",
        "tushare": "XSHG",
        "yfinance": None,
    }

    holidays: Optional[pd.DatetimeIndex] = None
    exchange: Optional[str] = None

    @classmethod
    def for_source(cls, source: Optional[str]) -> "TradingCalendar":
        """Build a default calendar for a configured market data source."""
        normalized = str(source or "").strip().lower()
        return cls(exchange=cls.SOURCE_EXCHANGE_MAP.get(normalized))

    def sessions(self, start: str, end: str) -> pd.DatetimeIndex:
        """Return trading sessions between start and end (inclusive)."""
        sessions = self._exchange_sessions(start, end) if self.exchange else pd.bdate_range(start=start, end=end)
        if self.holidays is None or len(self.holidays) == 0:
            return sessions
        return sessions.difference(self.holidays)

    def _exchange_sessions(self, start: str, end: str) -> pd.DatetimeIndex:
        """Return exchange sessions when an exchange calendar is configured."""
        try:
            sessions = _get_exchange_calendar(str(self.exchange)).sessions_in_range(start, end)
        except Exception:
            sessions = pd.bdate_range(start=start, end=end)
        return pd.to_datetime(sessions).normalize()


def normalize_holidays(holidays: Optional[Iterable[str]]) -> pd.DatetimeIndex:
    """Normalize holiday list into a DatetimeIndex."""
    if not holidays:
        return pd.DatetimeIndex([])
    return pd.to_datetime(list(holidays)).normalize()


def infer_missing_sessions(index: pd.DatetimeIndex, sessions: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Return sessions that are missing from the provided index."""
    if index.tz is not None:
        index = index.tz_localize(None)
    index = pd.to_datetime(index).normalize()
    return sessions.difference(index)


def align_frame_to_calendar(
    df: pd.DataFrame,
    sessions: pd.DatetimeIndex,
    *,
    fill_suspensions: bool = True,
) -> pd.DataFrame:
    """
    Align a single OHLCV frame to the trading calendar.

    When fill_suspensions is True, missing sessions are forward-filled using
    the previous close and volume is set to 0.0. A boolean 'suspended' column
    is added to flag filled rows.
    """
    if df is None or df.empty:
        return df
    out = df.copy()
    out.index = pd.to_datetime(out.index)
    if out.index.tz is not None:
        out.index = out.index.tz_localize(None)
    out = out.sort_index()

    missing_mask = ~out.index.isin(sessions)
    if missing_mask.any():
        # Drop rows outside expected sessions (e.g., weekends)
        out = out.loc[~missing_mask]

    out = out.reindex(sessions)
    missing_rows = out["close"].isna() if "close" in out.columns else out.isna().all(axis=1)
    if fill_suspensions:
        if "close" in out.columns:
            filled_close = out["close"].ffill()
            for col in ["open", "high", "low", "close"]:
                if col in out.columns:
                    out[col] = out[col].fillna(filled_close)
        else:
            out = out.ffill()
        if "volume" in out.columns:
            out["volume"] = out["volume"].fillna(0.0)
        out["suspended"] = missing_rows.fillna(False)
        # Drop leading rows without any data
        if "close" in out.columns:
            out = out.loc[out["close"].notna()]
    return out


def apply_trading_calendar(
    data_map: dict,
    *,
    start: str,
    end: str,
    calendar: Optional[TradingCalendar] = None,
    mode: str = "off",
) -> dict:
    """
    Apply trading calendar alignment to a map of OHLCV dataframes.

    mode:
      - "off": no alignment
      - "fill": align to sessions and fill missing bars (suspensions)
    """
    if not data_map or mode == "off":
        return data_map
    calendar = calendar or TradingCalendar()
    sessions = calendar.sessions(start, end)
    fill = mode == "fill"
    return {
        symbol: align_frame_to_calendar(df, sessions, fill_suspensions=fill)
        for symbol, df in data_map.items()
    }
