"""
Data Providers Module

Provides unified interfaces for loading stock data from multiple sources:
- AKShare (default)
- YFinance
- TuShare

Each provider implements the DataProvider interface for consistency.

V2.10.1 Update:
- Migrated from CSV file storage to SQLite3 database
- Intelligent incremental data fetching (only download missing ranges)
- Automatic data range detection and gap filling
"""
from __future__ import annotations

import hashlib
import logging
import os
import time
from typing import Dict, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from src.data_sources.db_manager import SQLiteDataManager

logger = logging.getLogger(__name__)

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

    def __init__(self, cache_dir: str = CACHE_DEFAULT):
        """
        Initialize data provider with SQLite database support.
        
        Args:
            cache_dir: Cache directory for database storage
        """
        self.cache_dir = cache_dir
        # Initialize database manager
        db_path = os.path.join(cache_dir, "market_data.db")
        self.db = SQLiteDataManager(db_path)

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

    def _fetch_stock_from_source(
        self,
        symbol: str,
        start: str,
        end: str,
        adj: Optional[str] = None,
    ) -> Optional[pd.DataFrame]:
        """
        Fetch stock data from remote source (to be implemented by subclasses).
        
        Args:
            symbol: Stock symbol
            start: Start date
            end: End date
            adj: Adjustment type
        
        Returns:
            DataFrame or None if fetch fails
        """
        raise NotImplementedError
    
    def _fetch_index_from_source(
        self,
        index_code: str,
        start: str,
        end: str,
    ) -> Optional[pd.DataFrame]:
        """
        Fetch index data from remote source (to be implemented by subclasses).
        
        Args:
            index_code: Index code
            start: Start date
            end: End date
        
        Returns:
            DataFrame or None if fetch fails
        """
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
        """
        Validate and normalize date format to YYYY-MM-DD.
        
        Args:
            start: Start date (YYYY-MM-DD or YYYYMMDD)
            end: End date (YYYY-MM-DD or YYYYMMDD)
        
        Returns:
            Tuple of normalized dates in YYYY-MM-DD format
        """
        if not start or not end:
            raise ValueError("start and end dates are required")
        
        # Normalize to YYYY-MM-DD format
        start_clean = start.replace("/", "-")
        if "-" not in start_clean and len(start_clean) == 8:
            # Convert YYYYMMDD to YYYY-MM-DD
            start_clean = f"{start_clean[:4]}-{start_clean[4:6]}-{start_clean[6:8]}"
        
        end_clean = end.replace("/", "-")
        if "-" not in end_clean and len(end_clean) == 8:
            end_clean = f"{end_clean[:4]}-{end_clean[4:6]}-{end_clean[6:8]}"
        
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


def _data_checksum(df: pd.DataFrame) -> Optional[str]:
    """Compute a checksum for a dataframe."""
    if df is None or df.empty:
        return None
    frame = df.copy()
    frame.index = pd.to_datetime(frame.index)
    frame = frame.sort_index()
    hash_values = pd.util.hash_pandas_object(frame, index=True).values
    return hashlib.sha256(hash_values.tobytes()).hexdigest()


# ---------------------------------------------------------------------------
# AKShare Provider
# ---------------------------------------------------------------------------

class AkshareProvider(DataProvider):
    """Load stock/index data from AKShare with SQLite3 caching."""

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
        """
        Load daily OHLCV data for multiple stocks.
        
        Uses SQLite3 database for caching. Only fetches missing data ranges.
        """
        try:
            import akshare as ak
        except ImportError as exc:
            raise DataProviderUnavailable("akshare not available") from exc

        self._ensure_cache(cache_dir)
        start_clean, end_clean = self._validate_dates(start, end)
        
        # AKShare expects: "qfq" (前复权), "hfq" (后复权), "" (不复权)
        adj_type = "noadj"
        adj_str = ""
        if adj and adj.lower() in ["qfq", "hfq"]:
            adj_str = adj.lower()
            adj_type = adj_str

        result = {}
        for symbol in symbols:
            try:
                # Check database for existing data
                logger.info(f"Loading {symbol} from database...")
                existing_df = self.db.load_stock_data(symbol, start_clean, end_clean, adj_type)
                logger.info(f"Existing data loaded: {existing_df is not None}")
                
                # Check for missing ranges
                missing_ranges = self.db.get_missing_ranges(
                    symbol, 'stock', start_clean, end_clean, adj_type
                )
                
                if not missing_ranges:
                    # All data available in database
                    if existing_df is not None and not existing_df.empty:
                        logger.info(f"✓ {symbol}: Loaded from database ({len(existing_df)} bars)")
                        result[symbol] = existing_df
                        continue
                
                # Fetch missing data from AKShare
                logger.info(f"↓ {symbol}: Fetching {len(missing_ranges)} missing range(s) from AKShare")
                
                for fetch_start, fetch_end in missing_ranges:
                    df_new = self._fetch_stock_from_source(symbol, fetch_start, fetch_end, adj_str)
                    if df_new is not None and not df_new.empty:
                        # Save to database
                        self.db.save_stock_data(symbol, df_new, adj_type)
                        # Record lineage
                        checksum = _data_checksum(df_new)
                        self.db.record_lineage(
                            symbol=symbol,
                            data_type="stock",
                            adj_type=adj_type,
                            source=self.name,
                            start_date=str(df_new.index.min().date()),
                            end_date=str(df_new.index.max().date()),
                            record_count=len(df_new),
                            checksum=checksum,
                        )
                        logger.debug(f"  Saved {len(df_new)} bars for range {fetch_start} to {fetch_end}")
                
                # Load complete data from database
                final_df = self.db.load_stock_data(symbol, start_clean, end_clean, adj_type)
                
                if final_df is not None and not final_df.empty:
                    result[symbol] = final_df
                    logger.info(f"✓ {symbol}: Complete ({len(final_df)} bars)")
                else:
                    logger.warning(f"✗ {symbol}: No data available")
                    
            except Exception as e:
                import traceback
                logger.error(f"✗ {symbol}: Error loading data: {e}")
                logger.debug(traceback.format_exc())
                continue

        return result
    
    def _fetch_stock_from_source(
        self,
        symbol: str,
        start: str,
        end: str,
        adj: Optional[str] = None,
    ) -> Optional[pd.DataFrame]:
        """
        Fetch stock data from AKShare API.
        
        Args:
            symbol: Stock symbol (e.g., "600519.SH")
            start: Start date
            end: End date
            adj: Adjustment type ("qfq", "hfq", or empty)
        
        Returns:
            Standardized DataFrame or None
        """
        try:
            import akshare as ak
        except ImportError:
            return None
        
        # AKShare expects pure symbol without exchange suffix
        ak_symbol = symbol.replace(".SH", "").replace(".SZ", "")
        
        try:
            df = ak.stock_zh_a_hist(
                symbol=ak_symbol,
                period="daily",
                start_date=start.replace("-", ""),
                end_date=end.replace("-", ""),
                adjust=adj or "",
            )

            if df is None or df.empty:
                return None

            df = _standardize_stock_frame(df)

            # Filter to requested date range
            df = df.loc[start:end]
            return df
        except Exception as e:
            logger.error(f"AKShare fetch error for {symbol}: {e}")
            return None


    def load_index_nav(
        self,
        index_code: str,
        start: str,
        end: str,
        *,
        cache_dir: str = CACHE_DEFAULT,
    ) -> pd.Series:
        """
        Load index data and convert to NAV series.
        
        Uses SQLite3 database for caching with incremental updates.
        """
        try:
            import akshare as ak
        except ImportError as exc:
            raise DataProviderUnavailable("akshare not available") from exc

        self._ensure_cache(cache_dir)
        start_clean, end_clean = self._validate_dates(start, end)
        adj_type = "noadj"  # Indexes don't have adjustments

        try:
            # Check database for existing data
            existing_df = self.db.load_index_data(index_code, start_clean, end_clean, adj_type)
            
            # Check for missing ranges
            missing_ranges = self.db.get_missing_ranges(
                index_code, 'index', start_clean, end_clean, adj_type
            )
            
            if not missing_ranges:
                # All data available
                if existing_df is not None and not existing_df.empty:
                    logger.info(f"✓ Index {index_code}: Loaded from database")
                    return _nav_from_close(existing_df["close"])
            
            # Fetch missing data
            logger.info(f"↓ Index {index_code}: Fetching {len(missing_ranges)} missing range(s)")
            
            for fetch_start, fetch_end in missing_ranges:
                df_new = self._fetch_index_from_source(index_code, fetch_start, fetch_end)
                if df_new is not None and not df_new.empty:
                    self.db.save_index_data(index_code, df_new, adj_type)
                    checksum = _data_checksum(df_new)
                    self.db.record_lineage(
                        symbol=index_code,
                        data_type="index",
                        adj_type=adj_type,
                        source=self.name,
                        start_date=str(df_new.index.min().date()),
                        end_date=str(df_new.index.max().date()),
                        record_count=len(df_new),
                        checksum=checksum,
                    )
            
            # Load complete data
            final_df = self.db.load_index_data(index_code, start_clean, end_clean, adj_type)
            
            if final_df is None or final_df.empty or "close" not in final_df.columns:
                raise DataProviderError(f"No data available for index {index_code}")
            
            return _nav_from_close(final_df["close"])
            
        except Exception as e:
            logger.error(f"Error loading index {index_code}: {e}")
            raise DataProviderError(f"Failed to load index {index_code}: {e}")
    
    def _fetch_index_from_source(
        self,
        index_code: str,
        start: str,
        end: str,
    ) -> Optional[pd.DataFrame]:
        """
        Fetch index data from AKShare API.
        
        Args:
            index_code: Index code (e.g., "000300.SH")
            start: Start date
            end: End date
        
        Returns:
            Standardized DataFrame or None
        """
        try:
            import akshare as ak
        except ImportError:
            return None
        
        # Convert index code to akshare format
        # e.g., 000300.SH -> sh000300, 399001.SZ -> sz399001
        ak_index_code = index_code
        if '.' in index_code:
            symbol, exchange = index_code.split('.')
            if exchange.upper() in ['SH', 'SS']:
                ak_index_code = f'sh{symbol}'
            elif exchange.upper() == 'SZ':
                ak_index_code = f'sz{symbol}'
        
        try:
            df = ak.stock_zh_index_daily(symbol=ak_index_code)
            
            if df is None or df.empty:
                return None
            
            df = _standardize_index_frame(df)
            
            # Filter to requested date range
            if not df.empty:
                df = df.loc[start:end]
            
            return df
            
        except Exception as e:
            logger.error(f"AKShare index fetch error for {index_code}: {e}")
            return None



# ---------------------------------------------------------------------------
# Qlib Provider (Local)
# ---------------------------------------------------------------------------

def _to_qlib_symbol(symbol: str) -> str:
    """Convert 600519.SH -> SH600519 for Qlib provider."""
    if not symbol:
        return symbol
    sym = symbol.strip().upper()
    if sym.startswith(("SH", "SZ")) and len(sym) > 2:
        return sym
    if sym.endswith(".SH"):
        return f"SH{sym[:-3]}"
    if sym.endswith(".SZ"):
        return f"SZ{sym[:-3]}"
    return sym


class QlibProvider(DataProvider):
    """Local Qlib data provider (offline)."""

    name: str = "qlib"
    _init_state: Tuple[Optional[str], Optional[str]] = (None, None)

    def __init__(self, cache_dir: str = CACHE_DEFAULT, provider_uri: Optional[str] = None, region: str = "cn"):
        super().__init__(cache_dir)
        self.provider_uri = provider_uri or os.environ.get("QLIB_DATA", "./qlib_data")
        self.region = region
        self._init_qlib()

    def _init_qlib(self) -> None:
        try:
            import qlib  # type: ignore
        except Exception as exc:
            raise DataProviderUnavailable("Qlib is not installed. Install pyqlib first.") from exc
        if self._init_state == (self.provider_uri, self.region):
            return
        qlib.init(provider_uri=self.provider_uri, region=self.region)
        self._init_state = (self.provider_uri, self.region)

    def load_stock_daily(
        self,
        symbols: Sequence[str],
        start: str,
        end: str,
        *,
        adj: Optional[str] = None,
        cache_dir: str = CACHE_DEFAULT,
    ) -> Dict[str, pd.DataFrame]:
        self._init_qlib()
        start_clean, end_clean = self._validate_dates(start, end)
        try:
            from qlib.data import D  # type: ignore
        except Exception as exc:
            raise DataProviderUnavailable("Qlib is not installed. Install pyqlib first.") from exc

        fields = ["$open", "$high", "$low", "$close", "$volume"]
        data_map: Dict[str, pd.DataFrame] = {}
        for symbol in symbols:
            qlib_symbol = _to_qlib_symbol(symbol)
            df = D.features([qlib_symbol], fields, start_time=start_clean, end_time=end_clean)
            if df is None or df.empty:
                continue
            frame = df.reset_index()
            frame = frame[frame["instrument"] == qlib_symbol]
            frame = frame.set_index("datetime")
            frame.index = pd.to_datetime(frame.index).tz_localize(None)
            frame = frame.rename(
                columns={
                    "$open": "open",
                    "$high": "high",
                    "$low": "low",
                    "$close": "close",
                    "$volume": "volume",
                }
            )
            frame.index.name = "date"
            data_map[symbol] = frame.sort_index()

        if not data_map:
            raise DataProviderError("Qlib provider returned no data. Check symbols and date range.")
        return data_map

    def load_index_nav(
        self,
        index_code: str,
        start: str,
        end: str,
        *,
        cache_dir: str = CACHE_DEFAULT,
    ) -> pd.Series:
        raise DataProviderError("QlibProvider does not support index NAV loading.")


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
    """Load stock/index data from Yahoo Finance via yfinance with SQLite3 caching."""

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
        """Load daily OHLCV data with intelligent caching."""
        try:
            import yfinance as yf
        except ImportError as exc:
            raise DataProviderUnavailable("yfinance not available") from exc

        self._ensure_cache(cache_dir)
        start_clean, end_clean = self._validate_dates(start, end)
        adj_type = "qfq" if adj == "qfq" else "noadj"

        result = {}
        for symbol in symbols:
            try:
                # Check database
                existing_df = self.db.load_stock_data(symbol, start_clean, end_clean, adj_type)
                missing_ranges = self.db.get_missing_ranges(
                    symbol, 'stock', start_clean, end_clean, adj_type
                )
                
                if not missing_ranges and existing_df is not None:
                    logger.info(f"✓ {symbol}: Loaded from database")
                    result[symbol] = existing_df
                    continue
                
                # Fetch missing data
                logger.info(f"↓ {symbol}: Fetching from YFinance")
                for fetch_start, fetch_end in missing_ranges:
                    df_new = self._fetch_stock_from_source(symbol, fetch_start, fetch_end, adj)
                    if df_new is not None:
                        self.db.save_stock_data(symbol, df_new, adj_type)
                        checksum = _data_checksum(df_new)
                        self.db.record_lineage(
                            symbol=symbol,
                            data_type="stock",
                            adj_type=adj_type,
                            source=self.name,
                            start_date=str(df_new.index.min().date()),
                            end_date=str(df_new.index.max().date()),
                            record_count=len(df_new),
                            checksum=checksum,
                        )
                        checksum = _data_checksum(df_new)
                        self.db.record_lineage(
                            symbol=symbol,
                            data_type="stock",
                            adj_type=adj_type,
                            source=self.name,
                            start_date=str(df_new.index.min().date()),
                            end_date=str(df_new.index.max().date()),
                            record_count=len(df_new),
                            checksum=checksum,
                        )
                
                # Load complete data
                final_df = self.db.load_stock_data(symbol, start_clean, end_clean, adj_type)
                if final_df is not None:
                    result[symbol] = final_df
                    
            except Exception as e:
                logger.error(f"✗ {symbol}: {e}")
                continue

        return result
    
    def _fetch_stock_from_source(
        self,
        symbol: str,
        start: str,
        end: str,
        adj: Optional[str] = None,
    ) -> Optional[pd.DataFrame]:
        """Fetch stock data from YFinance API."""
        try:
            import yfinance as yf
        except ImportError:
            return None
        
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start, end=end, auto_adjust=(adj == "qfq"))
            if df is None or df.empty:
                return None
            df = _standardize_yf(df)
            return df
        except Exception as e:
            logger.error(f"YFinance fetch error for {symbol}: {e}")
            return None

    def load_index_nav(
        self,
        index_code: str,
        start: str,
        end: str,
        *,
        cache_dir: str = CACHE_DEFAULT,
    ) -> pd.Series:
        """Load index data with SQLite3 caching."""
        try:
            import yfinance as yf
        except ImportError as exc:
            raise DataProviderUnavailable("yfinance not available") from exc

        self._ensure_cache(cache_dir)
        start_clean, end_clean = self._validate_dates(start, end)
        adj_type = "noadj"

        try:
            # Check database
            existing_df = self.db.load_index_data(index_code, start_clean, end_clean, adj_type)
            missing_ranges = self.db.get_missing_ranges(
                index_code, 'index', start_clean, end_clean, adj_type
            )
            
            if not missing_ranges and existing_df is not None:
                return _nav_from_close(existing_df["close"])
            
            # Fetch missing data
            for fetch_start, fetch_end in missing_ranges:
                df_new = self._fetch_index_from_source(index_code, fetch_start, fetch_end)
                if df_new is not None:
                    self.db.save_index_data(index_code, df_new, adj_type)
                    checksum = _data_checksum(df_new)
                    self.db.record_lineage(
                        symbol=index_code,
                        data_type="index",
                        adj_type=adj_type,
                        source=self.name,
                        start_date=str(df_new.index.min().date()),
                        end_date=str(df_new.index.max().date()),
                        record_count=len(df_new),
                        checksum=checksum,
                    )
                    checksum = _data_checksum(df_new)
                    self.db.record_lineage(
                        symbol=index_code,
                        data_type="index",
                        adj_type=adj_type,
                        source=self.name,
                        start_date=str(df_new.index.min().date()),
                        end_date=str(df_new.index.max().date()),
                        record_count=len(df_new),
                        checksum=checksum,
                    )
            
            # Load complete data
            final_df = self.db.load_index_data(index_code, start_clean, end_clean, adj_type)
            if final_df is None or "close" not in final_df.columns:
                raise DataProviderError(f"No data for index {index_code}")
            
            return _nav_from_close(final_df["close"])
            
        except Exception as e:
            raise DataProviderError(f"Failed to load index {index_code}: {e}")
    
    def _fetch_index_from_source(
        self,
        index_code: str,
        start: str,
        end: str,
    ) -> Optional[pd.DataFrame]:
        """Fetch index data from YFinance API."""
        try:
            import yfinance as yf
        except ImportError:
            return None
        
        try:
            ticker = yf.Ticker(index_code)
            df = ticker.history(start=start, end=end)
            if df is None or df.empty:
                return None
            df = _standardize_yf(df)
            return df
        except Exception as e:
            logger.error(f"YFinance index fetch error for {index_code}: {e}")
            return None


# ---------------------------------------------------------------------------
# TuShare Provider
# ---------------------------------------------------------------------------

class TuShareProvider(DataProvider):
    """Load stock/index data from TuShare (requires token) with SQLite3 caching."""

    name = "tushare"

    def __init__(self, token: Optional[str] = None, cache_dir: str = CACHE_DEFAULT):
        """Initialize TuShare provider with API token and database."""
        super().__init__(cache_dir)
        
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
        """Load daily OHLCV data with intelligent caching."""
        self._ensure_cache(cache_dir)
        start_clean, end_clean = self._validate_dates(start, end)
        adj_type = "qfq" if adj == "qfq" else "noadj"

        result = {}
        for symbol in symbols:
            try:
                # Check database
                existing_df = self.db.load_stock_data(symbol, start_clean, end_clean, adj_type)
                missing_ranges = self.db.get_missing_ranges(
                    symbol, 'stock', start_clean, end_clean, adj_type
                )
                
                if not missing_ranges and existing_df is not None:
                    logger.info(f"✓ {symbol}: Loaded from database")
                    result[symbol] = existing_df
                    continue
                
                # Fetch missing data
                logger.info(f"↓ {symbol}: Fetching from TuShare")
                for fetch_start, fetch_end in missing_ranges:
                    df_new = self._fetch_stock_from_source(symbol, fetch_start, fetch_end, adj)
                    if df_new is not None:
                        self.db.save_stock_data(symbol, df_new, adj_type)
                
                # Load complete data
                final_df = self.db.load_stock_data(symbol, start_clean, end_clean, adj_type)
                if final_df is not None:
                    result[symbol] = final_df
                    
            except Exception as e:
                logger.error(f"✗ {symbol}: {e}")
                continue

        return result
    
    def _fetch_stock_from_source(
        self,
        symbol: str,
        start: str,
        end: str,
        adj: Optional[str] = None,
    ) -> Optional[pd.DataFrame]:
        """Fetch stock data from TuShare API."""
        try:
            adj_factor = "qfq" if adj == "qfq" else None
            df = self.pro.daily(
                ts_code=symbol,
                start_date=start.replace("-", ""),
                end_date=end.replace("-", ""),
                adj=adj_factor,
            )
            
            if df is None or df.empty:
                return None
            
            # Standardize
            df = df.rename(columns={"trade_date": "date", "vol": "volume"})
            df["date"] = pd.to_datetime(df["date"])
            df.set_index("date", inplace=True)
            df = df.sort_index()
            
            return df
            
        except Exception as e:
            logger.error(f"TuShare fetch error for {symbol}: {e}")
            return None

    def load_index_nav(
        self,
        index_code: str,
        start: str,
        end: str,
        *,
        cache_dir: str = CACHE_DEFAULT,
    ) -> pd.Series:
        """Load index data with SQLite3 caching."""
        self._ensure_cache(cache_dir)
        start_clean, end_clean = self._validate_dates(start, end)
        adj_type = "noadj"

        try:
            # Check database
            existing_df = self.db.load_index_data(index_code, start_clean, end_clean, adj_type)
            missing_ranges = self.db.get_missing_ranges(
                index_code, 'index', start_clean, end_clean, adj_type
            )
            
            if not missing_ranges and existing_df is not None:
                return _nav_from_close(existing_df["close"])
            
            # Fetch missing data
            for fetch_start, fetch_end in missing_ranges:
                df_new = self._fetch_index_from_source(index_code, fetch_start, fetch_end)
                if df_new is not None:
                    self.db.save_index_data(index_code, df_new, adj_type)
            
            # Load complete data
            final_df = self.db.load_index_data(index_code, start_clean, end_clean, adj_type)
            if final_df is None or "close" not in final_df.columns:
                raise DataProviderError(f"No data for index {index_code}")
            
            return _nav_from_close(final_df["close"])
            
        except Exception as e:
            raise DataProviderError(f"Failed to load index {index_code}: {e}")
    
    def _fetch_index_from_source(
        self,
        index_code: str,
        start: str,
        end: str,
    ) -> Optional[pd.DataFrame]:
        """Fetch index data from TuShare API."""
        try:
            df = self.pro.index_daily(
                ts_code=index_code,
                start_date=start.replace("-", ""),
                end_date=end.replace("-", "")
            )
            
            if df is None or df.empty:
                return None
            
            df = df.rename(columns={"trade_date": "date"})
            df["date"] = pd.to_datetime(df["date"])
            df.set_index("date", inplace=True)
            df = df.sort_index()
            
            return df
            
        except Exception as e:
            logger.error(f"TuShare index fetch error for {index_code}: {e}")
            return None


# ---------------------------------------------------------------------------
# Factory Function
# ---------------------------------------------------------------------------
# Factory Function
# ---------------------------------------------------------------------------

def get_provider(name: str, cache_dir: str = CACHE_DEFAULT) -> DataProvider:
    """
    Factory function to create data provider instances.
    
    Args:
        name: Provider name ('akshare', 'yfinance', 'tushare')
        cache_dir: Cache directory for database storage
    
    Returns:
        DataProvider instance
    """
    if name == "akshare":
        return AkshareProvider(cache_dir)
    elif name == "yfinance":
        return YFinanceProvider(cache_dir)
    elif name == "tushare":
        return TuShareProvider(cache_dir=cache_dir)
    elif name == "qlib":
        return QlibProvider(cache_dir=cache_dir)
    else:
        raise ValueError(f"Unknown provider: {name}. Available: {PROVIDER_NAMES}")

# Export available provider names for CLI
PROVIDER_NAMES = ["akshare", "yfinance", "tushare", "qlib"]
