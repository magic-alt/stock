"""
Tests for SQLite3-based data caching system

Tests the new database-backed caching mechanism with incremental updates.
"""
import os
import tempfile
import shutil
from datetime import datetime, timedelta
import pandas as pd
import pytest

from src.data_sources.db_manager import SQLiteDataManager
from src.data_sources.providers import AkshareProvider, get_provider


class TestSQLiteDataManager:
    """Test SQLiteDataManager functionality."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, "test_market_data.db")
        manager = SQLiteDataManager(db_path)
        
        yield manager
        
        # Cleanup
        shutil.rmtree(temp_dir)
    
    def test_database_initialization(self, temp_db):
        """Test database schema creation."""
        # Check that database file was created
        assert os.path.exists(temp_db.db_path)
        
        # Verify tables exist
        import sqlite3
        with sqlite3.connect(temp_db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            assert 'stock_daily' in tables
            assert 'index_daily' in tables
            assert 'metadata' in tables
    
    def test_save_and_load_stock_data(self, temp_db):
        """Test saving and loading stock data."""
        # Create sample data
        dates = pd.date_range('2024-01-01', periods=10, freq='D')
        df = pd.DataFrame({
            'open': range(100, 110),
            'high': range(105, 115),
            'low': range(95, 105),
            'close': range(102, 112),
            'volume': [1000000] * 10
        }, index=dates)
        
        # Save data
        temp_db.save_stock_data('TEST.SH', df, 'noadj')
        
        # Load data
        loaded_df = temp_db.load_stock_data('TEST.SH', '2024-01-01', '2024-01-10', 'noadj')
        
        assert loaded_df is not None
        assert len(loaded_df) == 10
        assert 'close' in loaded_df.columns
        assert loaded_df['close'].iloc[0] == 102
    
    def test_save_and_load_index_data(self, temp_db):
        """Test saving and loading index data."""
        # Create sample data
        dates = pd.date_range('2024-01-01', periods=10, freq='D')
        df = pd.DataFrame({
            'close': range(3000, 3010)
        }, index=dates)
        
        # Save data
        temp_db.save_index_data('000300.SH', df, 'noadj')
        
        # Load data
        loaded_df = temp_db.load_index_data('000300.SH', '2024-01-01', '2024-01-10', 'noadj')
        
        assert loaded_df is not None
        assert len(loaded_df) == 10
        assert 'close' in loaded_df.columns
    
    def test_data_range_tracking(self, temp_db):
        """Test metadata tracking of data ranges."""
        # Create sample data
        dates = pd.date_range('2024-01-01', periods=10, freq='D')
        df = pd.DataFrame({
            'open': range(100, 110),
            'high': range(105, 115),
            'low': range(95, 105),
            'close': range(102, 112),
            'volume': [1000000] * 10
        }, index=dates)
        
        # Save data
        temp_db.save_stock_data('TEST.SH', df, 'noadj')
        
        # Check range
        data_range = temp_db.get_data_range('TEST.SH', 'stock', 'noadj')
        
        assert data_range is not None
        assert data_range[0] == '2024-01-01'
        assert data_range[1] == '2024-01-10'
    
    def test_missing_ranges_detection(self, temp_db):
        """Test detection of missing data ranges."""
        # Create sample data for part of the range
        dates = pd.date_range('2024-01-05', periods=5, freq='D')
        df = pd.DataFrame({
            'open': range(100, 105),
            'high': range(105, 110),
            'low': range(95, 100),
            'close': range(102, 107),
            'volume': [1000000] * 5
        }, index=dates)
        
        # Save data (only 2024-01-05 to 2024-01-09)
        temp_db.save_stock_data('TEST.SH', df, 'noadj')
        
        # Request wider range
        missing_ranges = temp_db.get_missing_ranges(
            'TEST.SH', 'stock', '2024-01-01', '2024-01-15', 'noadj'
        )
        
        # Should detect two missing ranges: before and after
        assert len(missing_ranges) == 2
        assert missing_ranges[0] == ('2024-01-01', '2024-01-04')
        assert missing_ranges[1] == ('2024-01-10', '2024-01-15')
    
    def test_incremental_update(self, temp_db):
        """Test incremental data updates."""
        # Save initial data
        dates1 = pd.date_range('2024-01-01', periods=5, freq='D')
        df1 = pd.DataFrame({
            'open': range(100, 105),
            'high': range(105, 110),
            'low': range(95, 100),
            'close': range(102, 107),
            'volume': [1000000] * 5
        }, index=dates1)
        temp_db.save_stock_data('TEST.SH', df1, 'noadj')
        
        # Save additional data
        dates2 = pd.date_range('2024-01-06', periods=5, freq='D')
        df2 = pd.DataFrame({
            'open': range(105, 110),
            'high': range(110, 115),
            'low': range(100, 105),
            'close': range(107, 112),
            'volume': [1000000] * 5
        }, index=dates2)
        temp_db.save_stock_data('TEST.SH', df2, 'noadj')
        
        # Load complete data
        loaded_df = temp_db.load_stock_data('TEST.SH', '2024-01-01', '2024-01-10', 'noadj')
        
        assert len(loaded_df) == 10
        assert loaded_df['close'].iloc[0] == 102
        assert loaded_df['close'].iloc[-1] == 111
    
    def test_adjustment_type_separation(self, temp_db):
        """Test that different adjustment types are stored separately."""
        dates = pd.date_range('2024-01-01', periods=5, freq='D')
        
        # Save noadj data
        df_noadj = pd.DataFrame({
            'open': range(100, 105),
            'high': range(105, 110),
            'low': range(95, 100),
            'close': range(102, 107),
            'volume': [1000000] * 5
        }, index=dates)
        temp_db.save_stock_data('TEST.SH', df_noadj, 'noadj')
        
        # Save qfq data (different prices)
        df_qfq = pd.DataFrame({
            'open': range(200, 205),
            'high': range(205, 210),
            'low': range(195, 200),
            'close': range(202, 207),
            'volume': [1000000] * 5
        }, index=dates)
        temp_db.save_stock_data('TEST.SH', df_qfq, 'qfq')
        
        # Load both types
        loaded_noadj = temp_db.load_stock_data('TEST.SH', '2024-01-01', '2024-01-05', 'noadj')
        loaded_qfq = temp_db.load_stock_data('TEST.SH', '2024-01-01', '2024-01-05', 'qfq')
        
        assert loaded_noadj['close'].iloc[0] == 102
        assert loaded_qfq['close'].iloc[0] == 202


class TestProviderIntegration:
    """Test provider integration with SQLite3 caching."""
    
    @pytest.fixture
    def temp_cache_dir(self):
        """Create temporary cache directory."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    def test_provider_initialization(self, temp_cache_dir):
        """Test that providers initialize with database."""
        provider = get_provider('akshare', cache_dir=temp_cache_dir)
        
        assert provider is not None
        assert provider.db is not None
        assert os.path.exists(provider.db.db_path)
    
    def test_incremental_fetch_logic(self, temp_cache_dir):
        """Test that providers only fetch missing ranges."""
        # This is a unit test without actual API calls
        # We'll mock the data fetching
        
        provider = AkshareProvider(temp_cache_dir)
        
        # Simulate existing data
        dates = pd.date_range('2024-01-05', periods=5, freq='D')
        df_existing = pd.DataFrame({
            'open': range(100, 105),
            'high': range(105, 110),
            'low': range(95, 100),
            'close': range(102, 107),
            'volume': [1000000] * 5
        }, index=dates)
        provider.db.save_stock_data('TEST.SH', df_existing, 'noadj')
        
        # Check missing ranges
        missing_ranges = provider.db.get_missing_ranges(
            'TEST.SH', 'stock', '2024-01-01', '2024-01-15', 'noadj'
        )
        
        # Should identify gaps
        assert len(missing_ranges) > 0
        assert any('2024-01-01' in r for r in missing_ranges)


def test_database_file_location():
    """Test that database is created in correct location."""
    cache_dir = "./test_cache_temp"
    os.makedirs(cache_dir, exist_ok=True)
    
    try:
        provider = get_provider('akshare', cache_dir=cache_dir)
        db_path = os.path.join(cache_dir, "market_data.db")
        
        assert os.path.exists(db_path)
        
    finally:
        # Cleanup
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
