# SQLite V2 Schema Guide

## Overview

Version 2.10.1.1 introduces an optimized database architecture with per-symbol tables. Instead of storing all stocks in a single `stock_daily` table, each stock/index now has its own dedicated table.

## Architecture

### Schema Comparison

**V2.10.1 (Old)**:
```
market_data.db
├── stock_daily       (all stocks: 600519.SH, 000001.SZ, ...)
├── index_daily       (all indexes: 000300.SH, ^GSPC, ...)
└── metadata          (tracking table)
```

**V2.10.1.1 (New)**:
```
market_data.db
├── stock_600519_SH   (贵州茅台)
├── stock_000001_SZ   (平安银行)
├── stock_600036_SH   (招商银行)
├── index_000300_SH   (沪深300)
├── index_GSPC        (S&P 500)
├── index_DJI         (Dow Jones)
├── index_HSI         (Hang Seng)
└── metadata          (enhanced tracking table)
```

### Benefits

1. **Performance**: No symbol filtering needed in queries
2. **International Support**: Handles diverse symbol formats (Chinese, US, HK)
3. **Simplicity**: Each table is independent and self-contained
4. **Maintenance**: Easy to export, import, or delete individual symbols

## Database Schema

### Metadata Table

Tracks all symbol tables and their data ranges:

```sql
CREATE TABLE metadata (
    symbol TEXT NOT NULL,           -- Symbol code (e.g., "600519.SH")
    data_type TEXT NOT NULL,        -- 'stock' or 'index'
    adj_type TEXT NOT NULL,         -- 'noadj', 'qfq', 'hfq'
    table_name TEXT NOT NULL,       -- Actual table name (e.g., "stock_600519_SH")
    start_date TEXT,                -- First date in data
    end_date TEXT,                  -- Last date in data
    record_count INTEGER DEFAULT 0, -- Number of records
    last_updated TEXT,              -- Last update timestamp
    PRIMARY KEY (symbol, data_type, adj_type)
)
```

### Stock Data Tables

Each stock has its own table:

```sql
CREATE TABLE stock_600519_SH (
    date TEXT NOT NULL PRIMARY KEY, -- Trading date (YYYY-MM-DD)
    open REAL,                      -- Open price
    high REAL,                      -- High price
    low REAL,                       -- Low price
    close REAL,                     -- Close price
    volume REAL,                    -- Trading volume
    adj_type TEXT                   -- Adjustment type
)
```

### Index Data Tables

Each index has its own table:

```sql
CREATE TABLE index_000300_SH (
    date TEXT NOT NULL PRIMARY KEY, -- Trading date (YYYY-MM-DD)
    close REAL,                     -- Close price
    adj_type TEXT                   -- Adjustment type
)
```

## Symbol Name Normalization

The `_normalize_table_name()` method converts symbol codes to valid SQL table names:

```python
# Chinese stocks
"600519.SH"  → "stock_600519_SH"
"000001.SZ"  → "stock_000001_SZ"

# Chinese indexes
"000300.SH"  → "index_000300_SH"
"399001.SZ"  → "index_399001_SZ"

# US indexes
"^GSPC"      → "index_GSPC"
"^DJI"       → "index_DJI"
"^IXIC"      → "index_IXIC"

# Hong Kong index
"^HSI"       → "index_HSI"
```

Rules:
- Replace `.` with `_`
- Remove `^` prefix
- Replace `-` with `_`
- Prefix with `stock_` or `index_`

## API Usage

### Basic Operations

```python
from src.data_sources.db_manager import SQLiteDataManager

# Initialize
db = SQLiteDataManager("./cache/market_data.db")

# Save stock data
import pandas as pd
df = pd.DataFrame({
    'open': [100, 101, 102],
    'high': [105, 106, 107],
    'low': [95, 96, 97],
    'close': [102, 103, 104],
    'volume': [1000000, 1100000, 1200000]
}, index=pd.date_range('2024-01-01', periods=3))

db.save_stock_data("600519.SH", df, "noadj")

# Load stock data
df = db.load_stock_data("600519.SH", "2024-01-01", "2024-01-31", "noadj")
print(df.head())
```

### International Indexes

```python
# S&P 500
db.save_index_data("^GSPC", sp500_df, "noadj")
sp500 = db.load_index_data("^GSPC", "2024-01-01", "2024-12-31", "noadj")

# Hang Seng Index
db.save_index_data("^HSI", hsi_df, "noadj")
hsi = db.load_index_data("^HSI", "2024-01-01", "2024-12-31", "noadj")

# CSI 300
db.save_index_data("000300.SH", csi300_df, "noadj")
csi300 = db.load_index_data("000300.SH", "2024-01-01", "2024-12-31", "noadj")
```

### Data Range & Incremental Updates

```python
# Check existing data range
date_range = db.get_data_range("600519.SH", "stock", "noadj")
if date_range:
    print(f"Data exists from {date_range[0]} to {date_range[1]}")

# Calculate missing ranges
missing = db.get_missing_ranges(
    "600519.SH", "stock", 
    "2023-01-01", "2024-12-31", 
    "noadj"
)
print(f"Need to download: {missing}")
# Output: [('2023-01-01', '2023-12-31'), ('2024-10-25', '2024-12-31')]
```

### Management Operations

```python
# List all symbols
stocks = db.get_all_symbols("stock")
indexes = db.get_all_symbols("index")

print(f"Total stocks: {len(stocks)}")
print(f"Total indexes: {len(indexes)}")

# Clear specific symbol
db.clear_symbol_data("600519.SH", "stock", "noadj")

# Optimize database
db.vacuum()
```

## CSV Import

### Import Single CSV

```python
# Import stock data
success = db.import_from_csv(
    csv_path="./cache/ak_600519.SH_2024-01-01_2024-12-31_noadj.csv",
    symbol="600519.SH",
    data_type="stock",
    adj_type="noadj"
)

# Import index data
success = db.import_from_csv(
    csv_path="./cache/ak_000300.SH_2024-01-01_2024-12-31_noadj.csv",
    symbol="000300.SH",
    data_type="index",
    adj_type="noadj"
)
```

### Batch Import from Cache

```python
# Import all CSV files from cache directory
stats = db.batch_import_from_cache("./cache")

print(f"Success: {stats['success']}")
print(f"Failed: {stats['failed']}")
print(f"Skipped: {stats['skipped']}")
print(f"Files: {stats['files']}")
```

### Supported CSV Formats

**English columns**:
```csv
date,open,high,low,close,volume
2024-01-01,100,105,95,102,1000000
2024-01-02,102,107,97,104,1100000
```

**Chinese columns** (from Akshare):
```csv
日期,开盘,最高,最低,收盘,成交量
2024-01-01,100,105,95,102,1000000
2024-01-02,102,107,97,104,1100000
```

Both formats are automatically recognized and imported correctly.

## Migration from V2.10.1

### Option 1: CSV Import (Recommended if you have cache files)

```python
from src.data_sources.db_manager import SQLiteDataManager

# Remove old database
import os
if os.path.exists("./cache/market_data.db"):
    os.remove("./cache/market_data.db")

# Create new database with V2 schema
db = SQLiteDataManager("./cache/market_data.db")

# Import all existing CSV files
stats = db.batch_import_from_cache("./cache")
print(f"Imported {stats['success']} files successfully")
```

### Option 2: Re-download Data

```python
# Simply delete the old database
import os
os.remove("./cache/market_data.db")

# Run your backtest - system will:
# 1. Create new database with V2 schema
# 2. Download required data
# 3. Save to per-symbol tables
```

### Option 3: Export-Import

```python
# From old database (V2.10.1)
old_db = SQLiteDataManager("./cache/market_data_old.db")
stocks = old_db.get_all_symbols("stock")

# Create new database (V2.10.1.1)
new_db = SQLiteDataManager("./cache/market_data.db")

# Transfer data
for symbol in stocks:
    df = old_db.load_stock_data(symbol, "2020-01-01", "2024-12-31", "noadj")
    if df is not None:
        new_db.save_stock_data(symbol, df, "noadj")
        print(f"Migrated {symbol}")
```

## Querying Database Directly

### Using SQLite CLI

```bash
# Open database
sqlite3 cache/market_data.db

# List all tables
.tables

# Check metadata
SELECT * FROM metadata LIMIT 10;

# Query specific stock
SELECT * FROM stock_600519_SH LIMIT 10;

# Count records per symbol
SELECT symbol, table_name, record_count 
FROM metadata 
ORDER BY record_count DESC;
```

### Using Python sqlite3

```python
import sqlite3
import pandas as pd

conn = sqlite3.connect("./cache/market_data.db")

# List all tables
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("Tables:", [t[0] for t in tables])

# Query metadata
meta_df = pd.read_sql_query("SELECT * FROM metadata", conn)
print(meta_df)

# Query specific stock
stock_df = pd.read_sql_query(
    "SELECT * FROM stock_600519_SH WHERE date >= '2024-01-01'", 
    conn
)
print(stock_df)

conn.close()
```

## Performance Tips

### 1. Use Date Indexes

All data tables have PRIMARY KEY on date column for fast date-based queries.

### 2. Vacuum Regularly

```python
# After deleting large amounts of data
db.vacuum()
```

### 3. Batch Operations

When inserting multiple symbols, commit in batches:

```python
symbols = ["600519.SH", "000001.SZ", "600036.SH"]
for symbol in symbols:
    df = fetch_data(symbol)  # Your data source
    db.save_stock_data(symbol, df, "noadj")
    # Each save_stock_data auto-commits
```

### 4. Query Optimization

```python
# Good: Use date range in query
df = db.load_stock_data("600519.SH", "2024-01-01", "2024-12-31", "noadj")

# Better: Query only what you need
# The load methods already use SELECT with date filtering
```

## Troubleshooting

### Table Naming Issues

**Problem**: Invalid characters in symbol code
```python
# This might fail if symbol has special chars
db.save_stock_data("SOME-SYMBOL.XX", df, "noadj")
```

**Solution**: The system auto-normalizes names
```python
# Automatically converts to: stock_SOME_SYMBOL_XX
# Just use the original symbol in API calls
```

### Missing Data After Import

**Problem**: CSV columns not recognized
```
ERROR: Missing columns in stock CSV: ['open', 'high', 'low', 'close', 'volume']
```

**Solution**: Check CSV format
```python
import pandas as pd
df = pd.read_csv("your_file.csv", nrows=5)
print(df.columns.tolist())

# If Chinese columns, they should be auto-mapped
# If custom columns, rename them before import
```

### Performance Degradation

**Problem**: Database queries slow
```python
# Check database size
import os
db_size = os.path.getsize("./cache/market_data.db") / (1024*1024)
print(f"Database size: {db_size:.2f} MB")
```

**Solution**: Vacuum database
```python
db.vacuum()
```

### Cannot Delete Old Database

**Problem**: Windows file lock
```
PermissionError: [WinError 32] 另一个程序正在使用此文件
```

**Solution**: Close all connections
```python
# Ensure all connections are closed
del db  # Delete db object
import gc
gc.collect()  # Force garbage collection

# Or restart Python
```

## Best Practices

### 1. One Database Per Project

```python
# Good: One database with multiple symbols
db = SQLiteDataManager("./cache/market_data.db")
db.save_stock_data("600519.SH", df1, "noadj")
db.save_stock_data("000001.SZ", df2, "noadj")

# Avoid: Multiple databases
db1 = SQLiteDataManager("./cache/stock1.db")
db2 = SQLiteDataManager("./cache/stock2.db")
```

### 2. Use Context Managers (in future versions)

```python
# Future enhancement
with SQLiteDataManager("./cache/market_data.db") as db:
    db.save_stock_data("600519.SH", df, "noadj")
# Auto-closes connection
```

### 3. Regular Backups

```bash
# Backup database daily
cp cache/market_data.db backups/market_data_$(date +%Y%m%d).db

# Or use SQLite backup command
sqlite3 cache/market_data.db ".backup backups/market_data_backup.db"
```

### 4. Monitor Database Size

```python
import os

db_path = "./cache/market_data.db"
size_mb = os.path.getsize(db_path) / (1024*1024)

if size_mb > 1000:  # > 1GB
    print(f"Warning: Database large ({size_mb:.0f} MB)")
    print("Consider archiving old data")
```

## Advanced Usage

### Custom Queries

```python
import sqlite3
import pandas as pd

conn = sqlite3.connect("./cache/market_data.db")

# Find top performing stocks in date range
query = """
SELECT 
    m.symbol,
    m.table_name,
    m.record_count,
    (SELECT close FROM {} WHERE date = m.end_date) as end_close,
    (SELECT close FROM {} WHERE date = m.start_date) as start_close
FROM metadata m
WHERE m.data_type = 'stock' 
  AND m.start_date <= '2024-01-01'
  AND m.end_date >= '2024-12-31'
"""

# Note: Can't directly parameterize table names, need dynamic query
# This is an example - production code should use the API methods
```

### Exporting to CSV

```python
# Export specific stock to CSV
df = db.load_stock_data("600519.SH", "2020-01-01", "2024-12-31", "noadj")
df.to_csv("600519_SH_export.csv")

# Export all stocks
stocks = db.get_all_symbols("stock")
for symbol in stocks:
    df = db.load_stock_data(symbol, "2020-01-01", "2024-12-31", "noadj")
    if df is not None:
        filename = f"{symbol.replace('.', '_')}_export.csv"
        df.to_csv(f"exports/{filename}")
```

### Concurrent Access

```python
# SQLite supports multiple readers
# But only one writer at a time

from concurrent.futures import ThreadPoolExecutor

# Good: Multiple reads
def read_stock(symbol):
    db = SQLiteDataManager("./cache/market_data.db")
    return db.load_stock_data(symbol, "2024-01-01", "2024-12-31", "noadj")

with ThreadPoolExecutor(max_workers=5) as executor:
    symbols = ["600519.SH", "000001.SZ", "600036.SH"]
    results = executor.map(read_stock, symbols)

# Avoid: Multiple writes (can cause lock errors)
# Write operations should be sequential
```

## Schema Evolution

Future versions may add:
- `adjusted_close` column for adjusted prices
- `split_ratio` column for stock splits
- `dividend` column for dividend data
- `metadata_v2` table for additional symbol information
- Support for intraday/tick data with separate tables

The per-symbol table architecture makes these additions easy to implement without breaking existing data.
