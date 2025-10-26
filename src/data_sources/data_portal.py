"""
DataPortal - Unified Data Access Layer

Provides a centralized interface for accessing market data with caching,
alignment, and normalization. Inspired by Zipline's DataPortal design.

Features:
- Unified API for historical and current data
- Automatic data alignment across symbols
- In-memory caching for performance
- Support for multiple data providers
- DataFrame and BarData object output
"""
from __future__ import annotations

import pandas as pd
from typing import Dict, List, Optional, Union, Sequence
from datetime import datetime, timedelta
import logging

from src.data_sources.providers import DataProvider, get_provider, PROVIDER_NAMES
from src.core.objects import BarData, Exchange, parse_symbol

logger = logging.getLogger(__name__)


class DataPortal:
    """
    Unified data access portal.
    
    Centralizes all market data access with caching and normalization.
    
    Usage:
        >>> portal = DataPortal(provider="akshare", cache_dir="./cache")
        >>> 
        >>> # Get current price
        >>> price = portal.current(["600519.SH"], "close")
        >>> 
        >>> # Get historical data
        >>> hist = portal.history(["600519.SH", "000001.SZ"], 
        ...                       ["open", "close"], 20)
        >>> 
        >>> # Get full dataset
        >>> data = portal.get_data(["600519.SH"], "2024-01-01", "2024-12-31")
    """
    
    def __init__(
        self,
        provider: Union[str, DataProvider] = "akshare",
        cache_dir: str = "./cache",
        adj: Optional[str] = None,
    ):
        """
        Initialize DataPortal.
        
        Args:
            provider: Data provider name or instance
            cache_dir: Cache directory path
            adj: Adjustment type ("qfq", "hfq", None)
        """
        # Initialize provider
        if isinstance(provider, str):
            self._provider = get_provider(provider)
        else:
            self._provider = provider
        
        self._cache_dir = cache_dir
        self._adj = adj
        
        # In-memory cache
        self._data_cache: Dict[str, pd.DataFrame] = {}
        self._current_data: Dict[str, pd.DataFrame] = {}
        
        # Current datetime cursor
        self._current_dt: Optional[datetime] = None
        
        logger.info(f"DataPortal initialized with provider={self._provider.name}")
    
    # -----------------------------------------------------------------------
    # Data Loading
    # -----------------------------------------------------------------------
    
    def load_data(
        self,
        symbols: Sequence[str],
        start: str,
        end: str,
        fields: Optional[List[str]] = None,
    ) -> Dict[str, pd.DataFrame]:
        """
        Load data for multiple symbols.
        
        Args:
            symbols: List of symbol identifiers
            start: Start date (YYYY-MM-DD)
            end: End date (YYYY-MM-DD)
            fields: Fields to load (None for all)
        
        Returns:
            Dictionary mapping symbol -> DataFrame
        """
        logger.info(f"Loading data for {len(symbols)} symbols from {start} to {end}")
        
        # Load data via provider
        data_map = self._provider.load_stock_daily(
            symbols, start, end, adj=self._adj, cache_dir=self._cache_dir
        )
        
        # Filter fields if specified
        if fields:
            data_map = {
                symbol: df[fields] if all(f in df.columns for f in fields) else df
                for symbol, df in data_map.items()
            }
        
        # Update cache
        self._data_cache.update(data_map)
        
        # Update current data (last bar for each symbol)
        for symbol, df in data_map.items():
            if not df.empty:
                self._current_data[symbol] = df
        
        return data_map
    
    def get_data(
        self,
        symbols: Sequence[str],
        start: str,
        end: str,
        fields: Optional[List[str]] = None,
        as_bars: bool = False,
    ) -> Union[Dict[str, pd.DataFrame], Dict[str, List[BarData]]]:
        """
        Get data for symbols in requested format.
        
        Args:
            symbols: List of symbols
            start: Start date
            end: End date
            fields: Fields to retrieve (None for all)
            as_bars: Return as BarData objects instead of DataFrame
        
        Returns:
            Dictionary of data (DataFrame or BarData list)
        """
        data_map = self.load_data(symbols, start, end, fields)
        
        if not as_bars:
            return data_map
        
        # Convert to BarData objects
        result = {}
        for symbol, df in data_map.items():
            code, exchange = parse_symbol(symbol)
            bars = []
            
            for idx, row in df.iterrows():
                bar = BarData(
                    symbol=symbol,
                    datetime=pd.to_datetime(idx),
                    exchange=exchange,
                    open=float(row.get("open", 0)),
                    high=float(row.get("high", 0)),
                    low=float(row.get("low", 0)),
                    close=float(row.get("close", 0)),
                    volume=float(row.get("volume", 0)),
                    interval="1d",
                    gateway_name=self._provider.name
                )
                bars.append(bar)
            
            result[symbol] = bars
        
        return result
    
    # -----------------------------------------------------------------------
    # Historical Data Access
    # -----------------------------------------------------------------------
    
    def history(
        self,
        symbols: Union[str, Sequence[str]],
        fields: Union[str, Sequence[str]],
        periods: int,
        end_dt: Optional[datetime] = None,
    ) -> Union[pd.Series, pd.DataFrame]:
        """
        Get historical data for symbols.
        
        Args:
            symbols: Single symbol or list of symbols
            fields: Single field or list of fields
            periods: Number of periods to look back
            end_dt: End datetime (None for current)
        
        Returns:
            Series (single symbol, single field) or DataFrame
        
        Examples:
            >>> # Single symbol, single field -> Series
            >>> closes = portal.history("600519.SH", "close", 20)
            >>> 
            >>> # Single symbol, multiple fields -> DataFrame with field columns
            >>> ohlc = portal.history("600519.SH", ["open", "close"], 20)
            >>> 
            >>> # Multiple symbols, single field -> DataFrame with symbol columns
            >>> closes = portal.history(["600519.SH", "000001.SZ"], "close", 20)
            >>> 
            >>> # Multiple symbols, multiple fields -> MultiIndex DataFrame
            >>> data = portal.history(["600519.SH"], ["open", "close"], 20)
        """
        # Normalize inputs
        is_single_symbol = isinstance(symbols, str)
        is_single_field = isinstance(fields, str)
        
        symbol_list = [symbols] if is_single_symbol else list(symbols)
        field_list = [fields] if is_single_field else list(fields)
        
        # Use end_dt or current datetime
        end = end_dt or self._current_dt or datetime.now()
        
        # Build result
        result_data = {}
        
        for symbol in symbol_list:
            # Get data from cache or load
            if symbol not in self._current_data:
                # Need to load data
                start = (end - timedelta(days=periods * 2)).strftime("%Y-%m-%d")
                end_str = end.strftime("%Y-%m-%d")
                self.load_data([symbol], start, end_str)
            
            df = self._current_data.get(symbol)
            if df is None or df.empty:
                continue
            
            # Filter by end datetime
            df_filtered = df[df.index <= end]
            
            # Get last N periods
            df_history = df_filtered.tail(periods)
            
            # Extract fields
            for field in field_list:
                if field in df_history.columns:
                    key = (symbol, field) if not is_single_symbol or not is_single_field else symbol
                    result_data[key] = df_history[field]
        
        if not result_data:
            # Return empty DataFrame/Series
            if is_single_symbol and is_single_field:
                return pd.Series(dtype=float)
            return pd.DataFrame()
        
        # Format output
        if is_single_symbol and is_single_field:
            # Single series
            return list(result_data.values())[0]
        elif is_single_symbol:
            # Single symbol, multiple fields -> DataFrame with field columns
            return pd.DataFrame(result_data)
        elif is_single_field:
            # Multiple symbols, single field -> DataFrame with symbol columns
            return pd.DataFrame(result_data)
        else:
            # Multiple symbols and fields -> MultiIndex DataFrame
            df = pd.DataFrame(result_data)
            df.columns = pd.MultiIndex.from_tuples(df.columns)
            return df
    
    # -----------------------------------------------------------------------
    # Current Data Access
    # -----------------------------------------------------------------------
    
    def current(
        self,
        symbols: Union[str, Sequence[str]],
        field: str = "close",
    ) -> Union[float, pd.Series]:
        """
        Get current value for symbols.
        
        Args:
            symbols: Single symbol or list of symbols
            field: Field to retrieve ("open", "high", "low", "close", "volume")
        
        Returns:
            Single value (if single symbol) or Series (if multiple symbols)
        
        Examples:
            >>> # Single symbol
            >>> price = portal.current("600519.SH", "close")  # 100.5
            >>> 
            >>> # Multiple symbols
            >>> prices = portal.current(["600519.SH", "000001.SZ"], "close")
            >>> # Series: 600519.SH -> 100.5, 000001.SZ -> 20.3
        """
        is_single = isinstance(symbols, str)
        symbol_list = [symbols] if is_single else list(symbols)
        
        result = {}
        for symbol in symbol_list:
            df = self._current_data.get(symbol)
            if df is not None and not df.empty and field in df.columns:
                # Get latest value
                if self._current_dt:
                    # Use cursor position
                    df_before = df[df.index <= self._current_dt]
                    if not df_before.empty:
                        result[symbol] = float(df_before[field].iloc[-1])
                else:
                    # Use last available
                    result[symbol] = float(df[field].iloc[-1])
        
        if is_single:
            return result.get(symbol_list[0], 0.0)
        
        return pd.Series(result)
    
    def current_bar(self, symbol: str) -> Optional[BarData]:
        """
        Get current bar for a symbol.
        
        Args:
            symbol: Symbol identifier
        
        Returns:
            BarData object or None
        """
        df = self._current_data.get(symbol)
        if df is None or df.empty:
            return None
        
        # Get current row
        if self._current_dt:
            df_before = df[df.index <= self._current_dt]
            if df_before.empty:
                return None
            row = df_before.iloc[-1]
            idx = df_before.index[-1]
        else:
            row = df.iloc[-1]
            idx = df.index[-1]
        
        code, exchange = parse_symbol(symbol)
        
        return BarData(
            symbol=symbol,
            datetime=pd.to_datetime(idx),
            exchange=exchange,
            open=float(row.get("open", 0)),
            high=float(row.get("high", 0)),
            low=float(row.get("low", 0)),
            close=float(row.get("close", 0)),
            volume=float(row.get("volume", 0)),
            interval="1d",
            gateway_name=self._provider.name
        )
    
    # -----------------------------------------------------------------------
    # Datetime Management
    # -----------------------------------------------------------------------
    
    def set_datetime(self, dt: datetime) -> None:
        """
        Set current datetime cursor.
        
        Used in backtesting to simulate time progression.
        
        Args:
            dt: Current datetime
        """
        self._current_dt = dt
    
    def get_datetime(self) -> Optional[datetime]:
        """Get current datetime cursor."""
        return self._current_dt
    
    # -----------------------------------------------------------------------
    # Cache Management
    # -----------------------------------------------------------------------
    
    def clear_cache(self) -> None:
        """Clear in-memory cache."""
        self._data_cache.clear()
        self._current_data.clear()
        logger.info("Cache cleared")
    
    def get_cached_symbols(self) -> List[str]:
        """Get list of cached symbols."""
        return list(self._current_data.keys())
    
    # -----------------------------------------------------------------------
    # Data Alignment
    # -----------------------------------------------------------------------
    
    def align_data(
        self,
        data_map: Dict[str, pd.DataFrame],
        method: str = "ffill"
    ) -> Dict[str, pd.DataFrame]:
        """
        Align data across symbols to common date index.
        
        Args:
            data_map: Dictionary of symbol -> DataFrame
            method: Fill method ("ffill", "bfill", "none")
        
        Returns:
            Aligned data dictionary
        """
        if not data_map:
            return {}
        
        # Get union of all dates
        all_dates = pd.DatetimeIndex([])
        for df in data_map.values():
            all_dates = all_dates.union(df.index)
        
        all_dates = all_dates.sort_values()
        
        # Reindex each DataFrame
        aligned = {}
        for symbol, df in data_map.items():
            df_aligned = df.reindex(all_dates)
            
            # Fill missing values
            if method == "ffill":
                df_aligned = df_aligned.fillna(method="ffill")
            elif method == "bfill":
                df_aligned = df_aligned.fillna(method="bfill")
            
            aligned[symbol] = df_aligned
        
        return aligned
    
    # -----------------------------------------------------------------------
    # Convenience Methods
    # -----------------------------------------------------------------------
    
    def can_trade(self, symbol: str) -> bool:
        """
        Check if symbol has data and can be traded.
        
        Args:
            symbol: Symbol identifier
        
        Returns:
            True if tradeable
        """
        return symbol in self._current_data and not self._current_data[symbol].empty
    
    def get_trading_dates(
        self,
        start: Optional[str] = None,
        end: Optional[str] = None
    ) -> pd.DatetimeIndex:
        """
        Get trading dates from cached data.
        
        Args:
            start: Start date filter
            end: End date filter
        
        Returns:
            DatetimeIndex of trading dates
        """
        if not self._current_data:
            return pd.DatetimeIndex([])
        
        # Get union of all dates
        all_dates = pd.DatetimeIndex([])
        for df in self._current_data.values():
            all_dates = all_dates.union(df.index)
        
        all_dates = all_dates.sort_values().unique()
        
        # Filter by date range
        if start:
            all_dates = all_dates[all_dates >= start]
        if end:
            all_dates = all_dates[all_dates <= end]
        
        return all_dates


# ---------------------------------------------------------------------------
# Factory Function
# ---------------------------------------------------------------------------

def create_portal(
    provider: str = "akshare",
    cache_dir: str = "./cache",
    adj: Optional[str] = None,
) -> DataPortal:
    """
    Factory function to create DataPortal instance.
    
    Args:
        provider: Data provider name
        cache_dir: Cache directory
        adj: Adjustment type
    
    Returns:
        DataPortal instance
    
    Example:
        >>> portal = create_portal("akshare", "./cache", adj="qfq")
    """
    return DataPortal(provider=provider, cache_dir=cache_dir, adj=adj)
