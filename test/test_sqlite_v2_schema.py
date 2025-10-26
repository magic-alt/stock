"""
Test suite for SQLite database V2 schema (per-symbol tables).
Tests the optimized database structure with individual tables for each stock/index.
"""

import os
import sys
import pytest
import pandas as pd
import tempfile
import shutil
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.data_sources.db_manager import SQLiteDataManager


class TestSQLiteV2Schema:
    """Test cases for optimized SQLite schema with per-symbol tables."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, "test_market_data.db")
        
        yield db_path
        
        # Cleanup
        try:
            if os.path.exists(db_path):
                os.remove(db_path)
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            print(f"Cleanup warning: {e}")
    
    @pytest.fixture
    def db_manager(self, temp_db):
        """Create database manager instance."""
        return SQLiteDataManager(temp_db)
    
    @pytest.fixture
    def sample_stock_data(self):
        """Create sample stock data."""
        dates = pd.date_range('2024-01-01', periods=10, freq='D')
        df = pd.DataFrame({
            'open': [100 + i for i in range(10)],
            'high': [105 + i for i in range(10)],
            'low': [95 + i for i in range(10)],
            'close': [102 + i for i in range(10)],
            'volume': [1000000 + i*10000 for i in range(10)]
        }, index=dates)
        return df
    
    @pytest.fixture
    def sample_index_data(self):
        """Create sample index data."""
        dates = pd.date_range('2024-01-01', periods=10, freq='D')
        df = pd.DataFrame({
            'close': [3000 + i*10 for i in range(10)]
        }, index=dates)
        return df
    
    def test_table_name_normalization(self, db_manager):
        """Test table name generation from symbols."""
        # Chinese stock
        assert db_manager._normalize_table_name("600519.SH", "stock") == "stock_600519_SH"
        assert db_manager._normalize_table_name("000001.SZ", "stock") == "stock_000001_SZ"
        
        # Index
        assert db_manager._normalize_table_name("000300.SH", "index") == "index_000300_SH"
        assert db_manager._normalize_table_name("^GSPC", "index") == "index_GSPC"
        assert db_manager._normalize_table_name("^DJI", "index") == "index_DJI"
    
    def test_stock_save_and_load(self, db_manager, sample_stock_data):
        """Test saving and loading stock data."""
        symbol = "600519.SH"
        
        # Save data
        db_manager.save_stock_data(symbol, sample_stock_data, "noadj")
        
        # Load data
        loaded = db_manager.load_stock_data(
            symbol, '2024-01-01', '2024-01-10', "noadj"
        )
        
        assert loaded is not None
        assert len(loaded) == 10
        assert list(loaded.columns) == ['open', 'high', 'low', 'close', 'volume']
        assert loaded['close'].iloc[0] == 102
    
    def test_index_save_and_load(self, db_manager, sample_index_data):
        """Test saving and loading index data."""
        symbol = "000300.SH"
        
        # Save data
        db_manager.save_index_data(symbol, sample_index_data, "noadj")
        
        # Load data
        loaded = db_manager.load_index_data(
            symbol, '2024-01-01', '2024-01-10', "noadj"
        )
        
        assert loaded is not None
        assert len(loaded) == 10
        assert 'close' in loaded.columns
        assert loaded['close'].iloc[0] == 3000
    
    def test_international_index_support(self, db_manager, sample_index_data):
        """Test support for international indexes."""
        # US indexes
        us_symbols = ["^GSPC", "^DJI", "^IXIC"]
        
        for symbol in us_symbols:
            db_manager.save_index_data(symbol, sample_index_data, "noadj")
            loaded = db_manager.load_index_data(symbol, '2024-01-01', '2024-01-10', "noadj")
            assert loaded is not None
            assert len(loaded) == 10
        
        # Hong Kong index
        db_manager.save_index_data("^HSI", sample_index_data, "noadj")
        loaded = db_manager.load_index_data("^HSI", '2024-01-01', '2024-01-10', "noadj")
        assert loaded is not None
    
    def test_metadata_tracking(self, db_manager, sample_stock_data):
        """Test metadata is properly tracked."""
        symbol = "600519.SH"
        
        # Save data
        db_manager.save_stock_data(symbol, sample_stock_data, "noadj")
        
        # Check data range
        date_range = db_manager.get_data_range(symbol, "stock", "noadj")
        assert date_range is not None
        assert date_range[0] == '2024-01-01'
        assert date_range[1] == '2024-01-10'
    
    def test_incremental_update(self, db_manager, sample_stock_data):
        """Test incremental data updates."""
        symbol = "600519.SH"
        
        # Save initial data
        db_manager.save_stock_data(symbol, sample_stock_data, "noadj")
        
        # Check missing ranges
        missing = db_manager.get_missing_ranges(
            symbol, "stock", "2023-12-25", "2024-01-15", "noadj"
        )
        
        # Should have two missing ranges: before and after
        assert len(missing) >= 1
        
        # Add more data
        new_dates = pd.date_range('2024-01-11', periods=5, freq='D')
        new_df = pd.DataFrame({
            'open': [110 + i for i in range(5)],
            'high': [115 + i for i in range(5)],
            'low': [105 + i for i in range(5)],
            'close': [112 + i for i in range(5)],
            'volume': [1100000 + i*10000 for i in range(5)]
        }, index=new_dates)
        
        db_manager.save_stock_data(symbol, new_df, "noadj")
        
        # Check updated range
        date_range = db_manager.get_data_range(symbol, "stock", "noadj")
        assert date_range[1] == '2024-01-15'
    
    def test_multiple_symbols(self, db_manager, sample_stock_data):
        """Test handling multiple symbols with separate tables."""
        symbols = ["600519.SH", "000001.SZ", "600036.SH"]
        
        for symbol in symbols:
            db_manager.save_stock_data(symbol, sample_stock_data, "noadj")
        
        # Load each symbol
        for symbol in symbols:
            loaded = db_manager.load_stock_data(
                symbol, '2024-01-01', '2024-01-10', "noadj"
            )
            assert loaded is not None
            assert len(loaded) == 10
        
        # Check all symbols are listed
        all_symbols = db_manager.get_all_symbols("stock")
        assert len(all_symbols) >= 3
        for symbol in symbols:
            assert symbol in all_symbols
    
    def test_clear_symbol_data(self, db_manager, sample_stock_data):
        """Test clearing symbol data drops the table."""
        symbol = "600519.SH"
        
        # Save data
        db_manager.save_stock_data(symbol, sample_stock_data, "noadj")
        
        # Verify data exists
        loaded = db_manager.load_stock_data(
            symbol, '2024-01-01', '2024-01-10', "noadj"
        )
        assert loaded is not None
        
        # Clear data
        db_manager.clear_symbol_data(symbol, "stock", "noadj")
        
        # Verify data is gone
        loaded = db_manager.load_stock_data(
            symbol, '2024-01-01', '2024-01-10', "noadj"
        )
        assert loaded is None
        
        # Verify no metadata
        date_range = db_manager.get_data_range(symbol, "stock", "noadj")
        assert date_range is None
    
    def test_nonexistent_symbol(self, db_manager):
        """Test loading data for nonexistent symbol."""
        loaded = db_manager.load_stock_data(
            "999999.SH", '2024-01-01', '2024-01-10', "noadj"
        )
        assert loaded is None


class TestCSVImport:
    """Test CSV import functionality."""
    
    @pytest.fixture
    def temp_env(self):
        """Create temporary environment with CSV files."""
        temp_dir = tempfile.mkdtemp()
        cache_dir = os.path.join(temp_dir, "cache")
        os.makedirs(cache_dir, exist_ok=True)
        
        db_path = os.path.join(temp_dir, "test_market_data.db")
        
        yield temp_dir, cache_dir, db_path
        
        # Cleanup
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            print(f"Cleanup warning: {e}")
    
    def create_sample_csv(self, cache_dir, symbol, data_type='stock'):
        """Create a sample CSV file."""
        dates = pd.date_range('2024-01-01', periods=10, freq='D')
        
        if data_type == 'stock':
            df = pd.DataFrame({
                'date': dates,
                'open': [100 + i for i in range(10)],
                'high': [105 + i for i in range(10)],
                'low': [95 + i for i in range(10)],
                'close': [102 + i for i in range(10)],
                'volume': [1000000 + i*10000 for i in range(10)]
            })
        else:
            df = pd.DataFrame({
                'date': dates,
                'close': [3000 + i*10 for i in range(10)]
            })
        
        filename = f"ak_{symbol}_2024-01-01_2024-01-10_noadj.csv"
        csv_path = os.path.join(cache_dir, filename)
        df.to_csv(csv_path, index=False)
        
        return csv_path
    
    def test_import_stock_csv(self, temp_env):
        """Test importing stock data from CSV."""
        temp_dir, cache_dir, db_path = temp_env
        
        # Create CSV
        csv_path = self.create_sample_csv(cache_dir, "600519.SH", "stock")
        
        # Import
        db_manager = SQLiteDataManager(db_path)
        result = db_manager.import_from_csv(csv_path, "600519.SH", "stock", "noadj")
        
        assert result is True
        
        # Verify data
        loaded = db_manager.load_stock_data("600519.SH", "2024-01-01", "2024-01-10", "noadj")
        assert loaded is not None
        assert len(loaded) == 10
    
    def test_import_index_csv(self, temp_env):
        """Test importing index data from CSV."""
        temp_dir, cache_dir, db_path = temp_env
        
        # Create CSV
        csv_path = self.create_sample_csv(cache_dir, "000300.SH", "index")
        
        # Import
        db_manager = SQLiteDataManager(db_path)
        result = db_manager.import_from_csv(csv_path, "000300.SH", "index", "noadj")
        
        assert result is True
        
        # Verify data
        loaded = db_manager.load_index_data("000300.SH", "2024-01-01", "2024-01-10", "noadj")
        assert loaded is not None
        assert len(loaded) == 10
    
    def test_batch_import(self, temp_env):
        """Test batch importing multiple CSV files."""
        temp_dir, cache_dir, db_path = temp_env
        
        # Create multiple CSV files
        symbols = ["600519.SH", "000001.SZ", "600036.SH"]
        for symbol in symbols:
            self.create_sample_csv(cache_dir, symbol, "stock")
        
        # Create index CSV
        self.create_sample_csv(cache_dir, "000300.SH", "index")
        
        # Batch import
        db_manager = SQLiteDataManager(db_path)
        stats = db_manager.batch_import_from_cache(cache_dir)
        
        assert stats['success'] >= 4
        assert stats['failed'] == 0
        
        # Verify all data imported
        for symbol in symbols:
            loaded = db_manager.load_stock_data(symbol, "2024-01-01", "2024-01-10", "noadj")
            assert loaded is not None
    
    def test_import_nonexistent_csv(self, temp_env):
        """Test importing from nonexistent CSV file."""
        temp_dir, cache_dir, db_path = temp_env
        
        db_manager = SQLiteDataManager(db_path)
        result = db_manager.import_from_csv(
            os.path.join(cache_dir, "nonexistent.csv"),
            "600519.SH", "stock", "noadj"
        )
        
        assert result is False


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])
