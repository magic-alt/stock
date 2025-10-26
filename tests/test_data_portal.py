"""
Tests for DataPortal

Validates unified data access functionality.
"""
from __future__ import annotations

import sys
sys.path.insert(0, "e:/work/Project/stock")

import pytest
import pandas as pd
from datetime import datetime, timedelta

from src.data_sources.data_portal import DataPortal, create_portal
from src.core.objects import BarData


class TestDataPortal:
    """Test DataPortal functionality."""
    
    @pytest.fixture
    def portal(self):
        """Create DataPortal instance for testing."""
        return create_portal("akshare", "./cache")
    
    def test_creation(self, portal):
        """Test DataPortal creation."""
        assert portal is not None
        assert portal._provider.name == "akshare"
    
    def test_load_data(self, portal):
        """Test loading data for symbols."""
        symbols = ["600519.SH"]
        start = "2024-01-01"
        end = "2024-01-31"
        
        data_map = portal.load_data(symbols, start, end)
        
        assert "600519.SH" in data_map
        assert not data_map["600519.SH"].empty
        assert "close" in data_map["600519.SH"].columns
        
        print(f"\nLoaded {len(data_map['600519.SH'])} bars for 600519.SH")
    
    def test_get_data_as_dataframe(self, portal):
        """Test get_data with DataFrame output."""
        data_map = portal.get_data(
            ["600519.SH"],
            "2024-01-01",
            "2024-01-31",
            fields=["open", "close"],
            as_bars=False
        )
        
        assert "600519.SH" in data_map
        df = data_map["600519.SH"]
        assert "open" in df.columns
        assert "close" in df.columns
    
    def test_get_data_as_bars(self, portal):
        """Test get_data with BarData output."""
        data_map = portal.get_data(
            ["600519.SH"],
            "2024-01-01",
            "2024-01-10",
            as_bars=True
        )
        
        assert "600519.SH" in data_map
        bars = data_map["600519.SH"]
        assert len(bars) > 0
        assert isinstance(bars[0], BarData)
        assert bars[0].symbol == "600519.SH"
        
        print(f"\nFirst bar: {bars[0].datetime}, close={bars[0].close}")
    
    def test_history_single_symbol_single_field(self, portal):
        """Test history for single symbol and field."""
        # Load data first
        portal.load_data(["600519.SH"], "2024-01-01", "2024-01-31")
        
        # Get history
        closes = portal.history("600519.SH", "close", 10)
        
        assert isinstance(closes, pd.Series)
        assert len(closes) <= 10
        
        print(f"\nLast 10 closes: {closes.values[-5:]}")
    
    def test_history_single_symbol_multiple_fields(self, portal):
        """Test history for single symbol, multiple fields."""
        portal.load_data(["600519.SH"], "2024-01-01", "2024-01-31")
        
        ohlc = portal.history("600519.SH", ["open", "high", "low", "close"], 5)
        
        assert isinstance(ohlc, pd.DataFrame)
        assert "open" in ohlc.columns
        assert "close" in ohlc.columns
        assert len(ohlc) <= 5
    
    def test_history_multiple_symbols(self, portal):
        """Test history for multiple symbols."""
        portal.load_data(["600519.SH", "000858.SZ"], "2024-01-01", "2024-01-31")
        
        closes = portal.history(["600519.SH", "000858.SZ"], "close", 5)
        
        assert isinstance(closes, pd.DataFrame)
        # Should have symbol columns or MultiIndex
        assert len(closes) <= 5
    
    def test_current_single_symbol(self, portal):
        """Test current price for single symbol."""
        portal.load_data(["600519.SH"], "2024-01-01", "2024-01-31")
        
        price = portal.current("600519.SH", "close")
        
        assert isinstance(price, float)
        assert price > 0
        
        print(f"\nCurrent price of 600519.SH: {price}")
    
    def test_current_multiple_symbols(self, portal):
        """Test current prices for multiple symbols."""
        portal.load_data(["600519.SH", "000858.SZ"], "2024-01-01", "2024-01-31")
        
        prices = portal.current(["600519.SH", "000858.SZ"], "close")
        
        assert isinstance(prices, pd.Series)
        assert "600519.SH" in prices.index
        
        print(f"\nCurrent prices: {prices}")
    
    def test_current_bar(self, portal):
        """Test getting current bar."""
        portal.load_data(["600519.SH"], "2024-01-01", "2024-01-31")
        
        bar = portal.current_bar("600519.SH")
        
        assert bar is not None
        assert isinstance(bar, BarData)
        assert bar.symbol == "600519.SH"
        assert bar.close > 0
        
        print(f"\nCurrent bar: {bar.datetime}, OHLC=({bar.open}, {bar.high}, {bar.low}, {bar.close})")
    
    def test_datetime_cursor(self, portal):
        """Test datetime cursor functionality."""
        portal.load_data(["600519.SH"], "2024-01-01", "2024-01-31")
        
        # Set cursor to middle of range
        cursor_dt = datetime(2024, 1, 15)
        portal.set_datetime(cursor_dt)
        
        assert portal.get_datetime() == cursor_dt
        
        # Current should respect cursor
        price = portal.current("600519.SH", "close")
        assert price > 0
    
    def test_can_trade(self, portal):
        """Test can_trade check."""
        portal.load_data(["600519.SH"], "2024-01-01", "2024-01-31")
        
        assert portal.can_trade("600519.SH") is True
        assert portal.can_trade("NONEXISTENT") is False
    
    def test_get_trading_dates(self, portal):
        """Test getting trading dates."""
        portal.load_data(["600519.SH"], "2024-01-01", "2024-01-31")
        
        dates = portal.get_trading_dates()
        
        assert len(dates) > 0
        assert isinstance(dates, pd.DatetimeIndex)
        
        print(f"\nTrading dates count: {len(dates)}")
        print(f"First date: {dates[0]}, Last date: {dates[-1]}")
    
    def test_align_data(self, portal):
        """Test data alignment."""
        # Load data for multiple symbols
        data_map = portal.load_data(
            ["600519.SH", "000858.SZ"],
            "2024-01-01",
            "2024-01-31"
        )
        
        # Align data
        aligned = portal.align_data(data_map, method="ffill")
        
        assert "600519.SH" in aligned
        assert "000858.SZ" in aligned
        
        # Should have same index
        idx1 = aligned["600519.SH"].index
        idx2 = aligned["000858.SZ"].index
        assert idx1.equals(idx2)
        
        print(f"\nAligned data shape: {aligned['600519.SH'].shape}")
    
    def test_cache_management(self, portal):
        """Test cache operations."""
        portal.load_data(["600519.SH"], "2024-01-01", "2024-01-31")
        
        # Check cached symbols
        cached = portal.get_cached_symbols()
        assert "600519.SH" in cached
        
        # Clear cache
        portal.clear_cache()
        cached_after = portal.get_cached_symbols()
        assert len(cached_after) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
