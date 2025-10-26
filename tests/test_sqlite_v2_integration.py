"""
Real-world integration test for SQLite V2 schema.
Tests with actual database and cache directory.
"""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.data_sources.db_manager import SQLiteDataManager


def test_csv_import_from_cache():
    """Test importing existing CSV files from cache directory."""
    
    # Use project's cache directory
    cache_dir = "./cache"
    db_path = "./cache/market_data_v2_test.db"
    
    # Remove old test database if exists
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
            print(f"Removed old test database: {db_path}")
        except Exception as e:
            print(f"Note: Could not remove old database ({e}), will overwrite")
    
    # Create database manager
    db_manager = SQLiteDataManager(db_path)
    print(f"\nDatabase created: {db_path}")
    
    # Import from cache
    print(f"\nImporting CSV files from {cache_dir}...")
    stats = db_manager.batch_import_from_cache(cache_dir)
    
    print(f"\n=== Import Statistics ===")
    print(f"Success: {stats['success']}")
    print(f"Failed: {stats['failed']}")
    print(f"Skipped: {stats['skipped']}")
    print(f"\nImported files:")
    for filename in stats['files'][:10]:  # Show first 10
        print(f"  - {filename}")
    if len(stats['files']) > 10:
        print(f"  ... and {len(stats['files']) - 10} more")
    
    # Test loading data from some symbols
    print(f"\n=== Testing Data Retrieval ===")
    test_symbols = [
        ("600519.SH", "stock"),
        ("000001.SZ", "stock"),
        ("000300.SH", "index"),
    ]
    
    for symbol, data_type in test_symbols:
        # Check data range
        date_range = db_manager.get_data_range(symbol, data_type, "noadj")
        if date_range:
            start, end = date_range
            print(f"\n{symbol} ({data_type}):")
            print(f"  Date range: {start} to {end}")
            
            # Load data
            if data_type == "stock":
                df = db_manager.load_stock_data(symbol, start, end, "noadj")
            else:
                df = db_manager.load_index_data(symbol, start, end, "noadj")
            
            if df is not None:
                print(f"  Records: {len(df)}")
                print(f"  First close: {df['close'].iloc[0]:.2f}")
                print(f"  Last close: {df['close'].iloc[-1]:.2f}")
        else:
            print(f"\n{symbol} ({data_type}): No data found")
    
    # Show all symbols in database
    print(f"\n=== Database Contents ===")
    stocks = db_manager.get_all_symbols("stock")
    indexes = db_manager.get_all_symbols("index")
    print(f"Total stocks: {len(stocks)}")
    print(f"Total indexes: {len(indexes)}")
    
    print(f"\nStocks (first 10):")
    for symbol in stocks[:10]:
        print(f"  - {symbol}")
    
    if indexes:
        print(f"\nIndexes:")
        for symbol in indexes[:10]:
            print(f"  - {symbol}")
    
    print(f"\n✓ Integration test completed successfully!")
    print(f"✓ Database file: {db_path}")
    
    return True


if __name__ == "__main__":
    test_csv_import_from_cache()
