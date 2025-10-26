"""
Data Providers Module

Provides unified interfaces for loading stock data from multiple sources:
- AKShare (default)
- YFinance
- TuShare

Each provider implements the DataProvider interface for consistency.
"""
from __future__ import annotations

import os
import time
from typing import Dict, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

CACHE_DEFAULT = "./cache"


# ---------------------------------------------------------------------------
# Base Classes and Exceptions
# ---------------------------------------------------------------------------

class DataProviderError(RuntimeError):
    """Raised when a data provider fails."""
    pass


class DataProviderUnavailable(DataProviderError):
    """Raised when an optional dependency is missing."""
    pass


class DataProvider:
    """Abstract base for OHLCV data providers."""

    name: str = "unknown"

    def load_stock_daily(
        self,
        symbols: Sequence[str],
        start: str,
        end: str,
        *,
        adj: Optional[str] = None,
        cache_dir: str = CACHE_DEFAULT,
    ) -> Dict[str, pd.DataFrame]:
        """Return OHLCV history in a consistent pandas format."""
        raise NotImplementedError

    def get_data(
        self,
        symbol: str,
        start: str,
        end: str,
        *,
        adj: Optional[str] = None,
        cache_dir: str = CACHE_DEFAULT,
    ) -> pd.DataFrame:
        """Convenience method to load data for a single symbol."""
        result = self.load_stock_daily([symbol], start, end, adj=adj, cache_dir=cache_dir)
        if symbol in result:
            return result[symbol]
        raise DataProviderError(f"Failed to load data for {symbol}")

    def load_index_nav(
        self,
        index_code: str,
        start: str,
        end: str,
        *,
        cache_dir: str = CACHE_DEFAULT,
    ) -> pd.Series:
        """Return a benchmark NAV series aligned with the date range."""
        raise NotImplementedError

    @staticmethod
    def _ensure_cache(cache_dir: str) -> None:
        """Create the cache directory if it does not already exist."""
        os.makedirs(cache_dir, exist_ok=True)

    @staticmethod
    def _validate_dates(start: str, end: str) -> Tuple[str, str]:
        """Ensure provider-friendly YYYYMMDD date strings."""
        if not start or not end:
            raise ValueError("start and end dates are required (YYYY-MM-DD)")
        start_clean = start.replace("-", "").replace("/", "")
        end_clean = end.replace("-", "").replace("/", "")
        return start_clean, end_clean


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def _standardize_stock_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize column names and types for stock OHLCV data."""
    df = df.copy()
    col_map = {
        "日期": "date", "开盘": "open", "收盘": "close",
        "最高": "high", "最低": "low", "成交量": "volume",
        "Date": "date", "Open": "open", "High": "high",
        "Low": "low", "Close": "close", "Volume": "volume",
    }
    df.rename(columns=col_map, inplace=True)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)
    df.index.name = "date"
    # Ensure timezone-naive index
    if hasattr(df.index, 'tz') and df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    for col in ["open", "high", "low", "close"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
    return df.sort_index()


def _standardize_index_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize index data (similar to stock but may have different column names)."""
    df = df.copy()
    
    # Map common column names to standard format
    col_map = {
        "日期": "date", 
        "收盘": "close", 
        "Close": "close",
        "close": "close",
        "Date": "date",
        "date": "date"
    }
    
    df.rename(columns=col_map, inplace=True)
    
    # Handle date column/index
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)
    elif df.index.name is None or df.index.name == "":
        # Try to convert index to datetime if it's not named
        try:
            df.index = pd.to_datetime(df.index)
            df.index.name = "date"
        except:
            # If first column looks like date, use it
            if len(df.columns) > 0:
                first_col = df.columns[0]
                try:
                    df[first_col] = pd.to_datetime(df[first_col])
                    df.set_index(first_col, inplace=True)
                    df.index.name = "date"
                except:
                    pass
    
    df.index.name = "date"
    
    # Ensure timezone-naive index
    if hasattr(df.index, 'tz') and df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    
    # Standardize close column
    if "close" in df.columns:
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
    elif "收盘" in df.columns:
        df["close"] = pd.to_numeric(df["收盘"], errors="coerce")
        df.drop(columns=["收盘"], inplace=True)
    
    return df.sort_index()


def _nav_from_close(close: pd.Series) -> pd.Series:
    """Normalize close prices into a NAV series starting at 1.0."""
    if close.empty:
        return close
    nav = close / close.iloc[0]
    nav.name = close.name or "benchmark"
    return nav


# ---------------------------------------------------------------------------
# AKShare Provider
# ---------------------------------------------------------------------------

class AkshareProvider(DataProvider):
    """Load stock/index data from AKShare."""

    name = "akshare"

    def load_stock_daily(
        self,
        symbols: Sequence[str],
        start: str,
        end: str,
        *,
        adj: Optional[str] = None,
        cache_dir: str = CACHE_DEFAULT,
    ) -> Dict[str, pd.DataFrame]:
        """Load daily OHLCV data for multiple stocks."""
        try:
            import akshare as ak
        except ImportError as exc:
            raise DataProviderUnavailable("akshare not available") from exc

        self._ensure_cache(cache_dir)
        start_clean, end_clean = self._validate_dates(start, end)
        # AKShare expects: "qfq" (前复权), "hfq" (后复权), "" (不复权)
        adj_str = ""  # Default to no adjustment
        if adj and adj.lower() in ["qfq", "hfq"]:
            adj_str = adj.lower()

        result = {}
        for symbol in symbols:
            # AKShare expects pure symbol without exchange suffix (e.g., "600519" not "600519.SH")
            ak_symbol = symbol.replace(".SH", "").replace(".SZ", "")
            
            cache_suffix = adj_str if adj_str else "noadj"
            cache_file = os.path.join(
                cache_dir, f"ak_{symbol}_{start}_{end}_{cache_suffix}.csv"
            )
            if os.path.exists(cache_file):
                # Try to read with index_col=0 first (standardized format)
                try:
                    df = pd.read_csv(cache_file, index_col=0, parse_dates=[0])
                    # Check if already standardized
                    if 'date' not in df.index.name and df.index.name != 'date':
                        # Not standardized, try to standardize
                        df = _standardize_stock_frame(df.reset_index())
                except Exception:
                    # Old format with Chinese columns, re-standardize
                    df = pd.read_csv(cache_file)
                    df = _standardize_stock_frame(df)
            else:
                try:
                    df = ak.stock_zh_a_hist(
                        symbol=ak_symbol,
                        period="daily",
                        start_date=start_clean,
                        end_date=end_clean,
                        adjust=adj_str,
                    )
                    if df.empty:
                        print(f"⚠️ {symbol}: AKShare returned empty DataFrame")
                        continue
                    df = _standardize_stock_frame(df)
                    if df.empty:
                        print(f"⚠️ {symbol}: DataFrame is empty after standardization")
                        continue
                    df.to_csv(cache_file)
                    time.sleep(0.3)
                except Exception as e:
                    import traceback
                    print(f"⚠️ Failed to load {symbol} from AKShare: {e}")
                    print(f"   Traceback: {traceback.format_exc()[:200]}")
                    continue

            if not df.empty:
                result[symbol] = df
            else:
                print(f"⚠️ {symbol}: DataFrame is empty after loading")

        return result

    def load_index_nav(
        self,
        index_code: str,
        start: str,
        end: str,
        *,
        cache_dir: str = CACHE_DEFAULT,
    ) -> pd.Series:
        """Load index data and convert to NAV series."""
        try:
            import akshare as ak
        except ImportError as exc:
            raise DataProviderUnavailable("akshare not available") from exc

        self._ensure_cache(cache_dir)
        start_clean, end_clean = self._validate_dates(start, end)

        # Convert index code to akshare format
        # e.g., 000300.SH -> sh000300, 399001.SZ -> sz399001
        ak_index_code = index_code
        if '.' in index_code:
            symbol, exchange = index_code.split('.')
            if exchange.upper() in ['SH', 'SS']:
                ak_index_code = f'sh{symbol}'
            elif exchange.upper() == 'SZ':
                ak_index_code = f'sz{symbol}'

        cache_file = os.path.join(
            cache_dir, f"ak_index_{index_code}_{start_clean}_{end_clean}.csv"
        )

        if os.path.exists(cache_file):
            try:
                # Try reading with index_col=0 (standardized format)
                df = pd.read_csv(cache_file, index_col=0, parse_dates=[0])
                # Ensure index name is 'date'
                if df.index.name != 'date':
                    df.index.name = 'date'
            except Exception:
                # Fallback: re-standardize from raw data
                df = pd.read_csv(cache_file)
                df = _standardize_index_frame(df)
        else:
            try:
                df = ak.stock_zh_index_daily(symbol=ak_index_code)
                if df.empty:
                    raise DataProviderError(f"AKShare returned empty data for {index_code}")
                df = _standardize_index_frame(df)
                # Filter date range
                if not df.empty:
                    df = df.loc[start_clean:end_clean]
                df.to_csv(cache_file)
            except Exception as e:
                raise DataProviderError(f"Failed to load index {index_code}: {e}")

        if df.empty or "close" not in df.columns:
            raise DataProviderError(f"No close price data for index {index_code}")

        return _nav_from_close(df["close"])


# ---------------------------------------------------------------------------
# YFinance Provider
# ---------------------------------------------------------------------------

def _standardize_yf(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize yfinance DataFrame."""
    df = df.copy()
    # yfinance returns MultiIndex columns for multiple tickers
    if isinstance(df.columns, pd.MultiIndex):
        # Flatten: e.g., ('Close', 'AAPL') -> 'Close'
        df.columns = df.columns.get_level_values(0)

    col_map = {
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
    }
    df.rename(columns=col_map, inplace=True)
    df.index = pd.to_datetime(df.index)
    df.index.name = "date"
    # Ensure timezone-naive index
    if hasattr(df.index, 'tz') and df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    for col in ["open", "high", "low", "close"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)

    return df.dropna(subset=["close"]).sort_index()


class YFinanceProvider(DataProvider):
    """Load stock/index data from Yahoo Finance via yfinance."""

    name = "yfinance"

    def load_stock_daily(
        self,
        symbols: Sequence[str],
        start: str,
        end: str,
        *,
        adj: Optional[str] = None,
        cache_dir: str = CACHE_DEFAULT,
    ) -> Dict[str, pd.DataFrame]:
        """Load daily OHLCV data for multiple stocks."""
        try:
            import yfinance as yf
        except ImportError as exc:
            raise DataProviderUnavailable("yfinance not available") from exc

        self._ensure_cache(cache_dir)
        result = {}

        for symbol in symbols:
            cache_file = os.path.join(
                cache_dir, f"yf_{symbol}_{start}_{end}.csv"
            )

            if os.path.exists(cache_file):
                df = pd.read_csv(cache_file, parse_dates=["date"], index_col="date")
            else:
                try:
                    ticker = yf.Ticker(symbol)
                    df = ticker.history(start=start, end=end, auto_adjust=(adj == "qfq"))
                    df = _standardize_yf(df)
                    df.to_csv(cache_file)
                    time.sleep(0.2)
                except Exception as e:
                    print(f"⚠️ Failed to load {symbol} from YFinance: {e}")
                    continue

            if not df.empty:
                result[symbol] = df

        return result

    def load_index_nav(
        self,
        index_code: str,
        start: str,
        end: str,
        *,
        cache_dir: str = CACHE_DEFAULT,
    ) -> pd.Series:
        """Load index data and convert to NAV series."""
        try:
            import yfinance as yf
        except ImportError as exc:
            raise DataProviderUnavailable("yfinance not available") from exc

        self._ensure_cache(cache_dir)
        cache_file = os.path.join(
            cache_dir, f"yf_index_{index_code}_{start}_{end}.csv"
        )

        if os.path.exists(cache_file):
            df = pd.read_csv(cache_file, parse_dates=["date"], index_col="date")
        else:
            try:
                ticker = yf.Ticker(index_code)
                df = ticker.history(start=start, end=end)
                df = _standardize_yf(df)
                df.to_csv(cache_file)
            except Exception as e:
                raise DataProviderError(f"Failed to load index {index_code}: {e}")

        if "close" not in df.columns or df.empty:
            raise DataProviderError(f"No close price data for index {index_code}")

        return _nav_from_close(df["close"])


# ---------------------------------------------------------------------------
# TuShare Provider
# ---------------------------------------------------------------------------

class TuShareProvider(DataProvider):
    """Load stock/index data from TuShare (requires token)."""

    name = "tushare"

    def __init__(self, token: Optional[str] = None):
        """Initialize TuShare provider with API token."""
        try:
            import tushare as ts
        except ImportError as exc:
            raise DataProviderUnavailable("tushare not available") from exc

        self.token = token or os.getenv("TUSHARE_TOKEN")
        if not self.token:
            raise DataProviderError(
                "TuShare token required (set TUSHARE_TOKEN env var or pass token)"
            )

        ts.set_token(self.token)
        self.pro = ts.pro_api()

    def load_stock_daily(
        self,
        symbols: Sequence[str],
        start: str,
        end: str,
        *,
        adj: Optional[str] = None,
        cache_dir: str = CACHE_DEFAULT,
    ) -> Dict[str, pd.DataFrame]:
        """Load daily OHLCV data for multiple stocks."""
        self._ensure_cache(cache_dir)
        start_clean, end_clean = self._validate_dates(start, end)

        result = {}
        adj_factor = "qfq" if adj == "qfq" else None

        for symbol in symbols:
            cache_file = os.path.join(
                cache_dir, f"ts_{symbol}_{start_clean}_{end_clean}_{adj or 'noadj'}.csv"
            )

            if os.path.exists(cache_file):
                df = pd.read_csv(cache_file, parse_dates=["date"], index_col="date")
            else:
                try:
                    df = self.pro.daily(
                        ts_code=symbol,
                        start_date=start_clean,
                        end_date=end_clean,
                        adj=adj_factor,
                    )
                    if df.empty:
                        continue

                    df = df.rename(columns={"trade_date": "date", "vol": "volume"})
                    df["date"] = pd.to_datetime(df["date"])
                    df.set_index("date", inplace=True)
                    df = df.sort_index()
                    df.to_csv(cache_file)
                    time.sleep(0.3)
                except Exception as e:
                    print(f"⚠️ Failed to load {symbol} from TuShare: {e}")
                    continue

            if not df.empty:
                result[symbol] = df

        return result

    def load_index_nav(
        self,
        index_code: str,
        start: str,
        end: str,
        *,
        cache_dir: str = CACHE_DEFAULT,
    ) -> pd.Series:
        """Load index data and convert to NAV series."""
        self._ensure_cache(cache_dir)
        start_clean, end_clean = self._validate_dates(start, end)

        cache_file = os.path.join(
            cache_dir, f"ts_index_{index_code}_{start_clean}_{end_clean}.csv"
        )

        if os.path.exists(cache_file):
            df = pd.read_csv(cache_file, parse_dates=["date"], index_col="date")
        else:
            try:
                df = self.pro.index_daily(
                    ts_code=index_code, start_date=start_clean, end_date=end_clean
                )
                df = df.rename(columns={"trade_date": "date"})
                df["date"] = pd.to_datetime(df["date"])
                df.set_index("date", inplace=True)
                df = df.sort_index()
                df.to_csv(cache_file)
            except Exception as e:
                raise DataProviderError(f"Failed to load index {index_code}: {e}")

        if "close" not in df.columns or df.empty:
            raise DataProviderError(f"No close price data for index {index_code}")

        return _nav_from_close(df["close"])


# ---------------------------------------------------------------------------
# Factory Function
# ---------------------------------------------------------------------------

_PROVIDER_FACTORIES = {
    "akshare": lambda: AkshareProvider(),
    "yfinance": lambda: YFinanceProvider(),
    "tushare": lambda: TuShareProvider(),
}

# Export available provider names for CLI
PROVIDER_NAMES = list(_PROVIDER_FACTORIES.keys())


def get_provider(name: str) -> DataProvider:
    """Factory function to create data provider instances."""
    if name not in _PROVIDER_FACTORIES:
        raise ValueError(f"Unknown provider: {name}. Available: {PROVIDER_NAMES}")
    return _PROVIDER_FACTORIES[name]()
