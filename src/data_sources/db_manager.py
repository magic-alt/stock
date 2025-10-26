"""
Database Manager for Market Data Storage

Provides SQLite3-based storage for stock and index data with intelligent caching.
Replaces CSV file storage with a more efficient database approach.

Features:
- SQLite3 database for persistent storage
- Automatic table creation and schema management
- Incremental data updates (only fetch missing ranges)
- Query existing data ranges to avoid redundant downloads
- Support for multiple symbols and data types
"""
from __future__ import annotations
import logging
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd

logger = logging.getLogger(__name__)


class SQLiteDataManager:
    """
    Manages SQLite3 database for market data storage.
    
    Optimized Schema V2:
        - Each stock has its own table: stock_<symbol> (e.g., stock_600519_SH)
        - Each index has its own table: index_<code> (e.g., index_000300_SH, index_HSI, index_NASDAQ)
        - metadata: Tracks all symbols and their table information
        
    Benefits:
        - Better performance (no symbol filtering needed)
        - Easier maintenance and querying
        - Support for different index types (A股, 港股, 美股指数等)
        - Simpler data import/export
    """
    
    def __init__(self, db_path: str = "./cache/market_data.db"):
        """
        Initialize database manager.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        
        # Initialize database schema
        self._init_schema()
        
        logger.info(f"SQLiteDataManager initialized: {db_path}")
    
    def _init_schema(self) -> None:
        """Create metadata table. Individual tables created on demand."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Metadata table for tracking all symbols and tables
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metadata (
                    symbol TEXT NOT NULL,
                    data_type TEXT NOT NULL,
                    adj_type TEXT NOT NULL,
                    table_name TEXT NOT NULL,
                    start_date TEXT,
                    end_date TEXT,
                    record_count INTEGER DEFAULT 0,
                    last_updated TEXT,
                    PRIMARY KEY (symbol, data_type, adj_type)
                )
            """)
            
            # Create index for faster lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_metadata_symbol 
                ON metadata (symbol, data_type)
            """)
            
            conn.commit()
    
    @staticmethod
    def _normalize_table_name(symbol: str, data_type: str) -> str:
        """
        Generate normalized table name from symbol.
        
        Args:
            symbol: Symbol code (e.g., "600519.SH", "000300.SH", "^GSPC")
            data_type: 'stock' or 'index'
        
        Returns:
            Normalized table name (e.g., "stock_600519_SH", "index_000300_SH")
        """
        # Remove special characters and replace with underscore
        normalized = symbol.replace(".", "_").replace("^", "").replace("-", "_")
        return f"{data_type}_{normalized}"
    
    def _create_stock_table(self, table_name: str) -> None:
        """Create table for individual stock."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    date TEXT NOT NULL PRIMARY KEY,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume REAL,
                    adj_type TEXT
                )
            """)
            # Create index on date
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{table_name}_date 
                ON {table_name} (date)
            """)
            conn.commit()
    
    def _create_index_table(self, table_name: str) -> None:
        """Create table for individual index."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    date TEXT NOT NULL PRIMARY KEY,
                    close REAL,
                    adj_type TEXT
                )
            """)
            # Create index on date
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{table_name}_date 
                ON {table_name} (date)
            """)
            conn.commit()
    
    # -----------------------------------------------------------------------
    # Stock Data Operations
    # -----------------------------------------------------------------------
    
    def save_stock_data(
        self,
        symbol: str,
        df: pd.DataFrame,
        adj_type: str = "noadj"
    ) -> None:
        """
        Save stock OHLCV data to database.
        
        Args:
            symbol: Stock symbol (e.g., "600519.SH")
            df: DataFrame with date index and OHLCV columns
            adj_type: Adjustment type (noadj, qfq, hfq)
        """
        if df.empty:
            return
        
        # Generate table name
        table_name = self._normalize_table_name(symbol, 'stock')
        
        # Create table if not exists
        self._create_stock_table(table_name)
        
        # Prepare data
        df = df.copy()
        df['adj_type'] = adj_type
        df['date'] = df.index.strftime('%Y-%m-%d')
        
        # Required columns
        columns = ['date', 'open', 'high', 'low', 'close', 'volume', 'adj_type']
        
        with sqlite3.connect(self.db_path) as conn:
            # Insert or replace data
            for _, row in df[columns].iterrows():
                conn.execute(f"""
                    INSERT OR REPLACE INTO {table_name} 
                    (date, open, high, low, close, volume, adj_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, tuple(row))
            
            # Update metadata
            self._update_metadata(
                conn, symbol, 'stock', adj_type, table_name,
                df.index.min(), df.index.max(), len(df)
            )
            
            conn.commit()
        
        logger.debug(f"Saved {len(df)} rows for {symbol} to table {table_name}")
    
    def load_stock_data(
        self,
        symbol: str,
        start: str,
        end: str,
        adj_type: str = "noadj"
    ) -> Optional[pd.DataFrame]:
        """
        Load stock data from database.
        
        Args:
            symbol: Stock symbol
            start: Start date (YYYY-MM-DD)
            end: End date (YYYY-MM-DD)
            adj_type: Adjustment type
        
        Returns:
            DataFrame with date index, or None if no data
        """
        table_name = self._normalize_table_name(symbol, 'stock')
        
        # Check if table exists
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name=?
            """, (table_name,))
            if not cursor.fetchone():
                return None
        
        query = f"""
            SELECT date, open, high, low, close, volume
            FROM {table_name}
            WHERE adj_type = ? AND date >= ? AND date <= ?
            ORDER BY date
        """
        
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(query, conn, params=(adj_type, start, end))
        
        if df.empty:
            return None
        
        # Set index
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        return df
    
    # -----------------------------------------------------------------------
    # Index Data Operations
    # -----------------------------------------------------------------------
    
    def save_index_data(
        self,
        symbol: str,
        df: pd.DataFrame,
        adj_type: str = "noadj"
    ) -> None:
        """
        Save index data to database.
        
        Supports various index types:
        - A股指数: 000300.SH (沪深300), 000001.SH (上证指数), 399001.SZ (深证成指)
        - 港股指数: ^HSI (恒生指数)
        - 美股指数: ^GSPC (标普500), ^DJI (道琼斯), ^IXIC (纳斯达克)
        
        Args:
            symbol: Index symbol
            df: DataFrame with date index and close column
            adj_type: Adjustment type
        """
        if df.empty:
            return
        
        # Generate table name
        table_name = self._normalize_table_name(symbol, 'index')
        
        # Create table if not exists
        self._create_index_table(table_name)
        
        # Prepare data
        df = df.copy()
        df['adj_type'] = adj_type
        df['date'] = df.index.strftime('%Y-%m-%d')
        
        # Required columns
        columns = ['date', 'close', 'adj_type']
        
        with sqlite3.connect(self.db_path) as conn:
            # Insert or replace data
            for _, row in df[columns].iterrows():
                conn.execute(f"""
                    INSERT OR REPLACE INTO {table_name} 
                    (date, close, adj_type)
                    VALUES (?, ?, ?)
                """, tuple(row))
            
            # Update metadata
            self._update_metadata(
                conn, symbol, 'index', adj_type, table_name,
                df.index.min(), df.index.max(), len(df)
            )
            
            conn.commit()
        
        logger.debug(f"Saved {len(df)} rows for index {symbol} to table {table_name}")
    
    def load_index_data(
        self,
        symbol: str,
        start: str,
        end: str,
        adj_type: str = "noadj"
    ) -> Optional[pd.DataFrame]:
        """
        Load index data from database.
        
        Args:
            symbol: Index symbol
            start: Start date (YYYY-MM-DD)
            end: End date (YYYY-MM-DD)
            adj_type: Adjustment type
        
        Returns:
            DataFrame with date index, or None if no data
        """
        table_name = self._normalize_table_name(symbol, 'index')
        
        # Check if table exists
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name=?
            """, (table_name,))
            if not cursor.fetchone():
                return None
        
        query = f"""
            SELECT date, close
            FROM {table_name}
            WHERE adj_type = ? AND date >= ? AND date <= ?
            ORDER BY date
        """
        
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(query, conn, params=(adj_type, start, end))
        
        if df.empty:
            return None
        
        # Set index
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        return df
    
    # -----------------------------------------------------------------------
    # Metadata and Range Operations
    # -----------------------------------------------------------------------
    
    def _update_metadata(
        self,
        conn: sqlite3.Connection,
        symbol: str,
        data_type: str,
        adj_type: str,
        table_name: str,
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        record_count: int
    ) -> None:
        """
        Update metadata for symbol.
        
        Args:
            conn: Database connection
            symbol: Symbol code
            data_type: 'stock' or 'index'
            adj_type: Adjustment type
            table_name: Name of the data table
            start_date: First date in data
            end_date: Last date in data
            record_count: Number of records
        """
        conn.execute("""
            INSERT OR REPLACE INTO metadata
            (symbol, data_type, adj_type, table_name, start_date, end_date, record_count, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            symbol, data_type, adj_type, table_name,
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d'),
            record_count,
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))
    
    def get_data_range(
        self,
        symbol: str,
        data_type: str,
        adj_type: str = "noadj"
    ) -> Optional[Tuple[str, str]]:
        """
        Get the date range of existing data.
        
        Args:
            symbol: Symbol identifier
            data_type: 'stock' or 'index'
            adj_type: Adjustment type
        
        Returns:
            Tuple of (start_date, end_date) or None if no data
        """
        query = """
            SELECT start_date, end_date
            FROM metadata
            WHERE symbol = ? AND data_type = ? AND adj_type = ?
        """
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, (symbol, data_type, adj_type))
            row = cursor.fetchone()
        
        if row:
            return (row[0], row[1])
        return None
    
    def get_missing_ranges(
        self,
        symbol: str,
        data_type: str,
        start: str,
        end: str,
        adj_type: str = "noadj"
    ) -> List[Tuple[str, str]]:
        """
        Calculate missing date ranges that need to be fetched.
        
        Args:
            symbol: Symbol identifier
            data_type: 'stock' or 'index'
            start: Requested start date
            end: Requested end date
            adj_type: Adjustment type
        
        Returns:
            List of (start, end) tuples for missing ranges
        """
        existing_range = self.get_data_range(symbol, data_type, adj_type)
        
        if not existing_range:
            # No data exists, fetch entire range
            return [(start, end)]
        
        existing_start, existing_end = existing_range
        
        # Convert to datetime for comparison
        req_start = datetime.strptime(start, '%Y-%m-%d')
        req_end = datetime.strptime(end, '%Y-%m-%d')
        exist_start = datetime.strptime(existing_start, '%Y-%m-%d')
        exist_end = datetime.strptime(existing_end, '%Y-%m-%d')
        
        missing_ranges = []
        
        # Check if we need data before existing range
        if req_start < exist_start:
            # Fetch from req_start to day before exist_start
            range_end = (exist_start - timedelta(days=1)).strftime('%Y-%m-%d')
            missing_ranges.append((start, range_end))
        
        # Check if we need data after existing range
        if req_end > exist_end:
            # Fetch from day after exist_end to req_end
            range_start = (exist_end + timedelta(days=1)).strftime('%Y-%m-%d')
            missing_ranges.append((range_start, end))
        
        return missing_ranges
    
    # -----------------------------------------------------------------------
    # Utility Methods
    # -----------------------------------------------------------------------
    
    def clear_symbol_data(
        self,
        symbol: str,
        data_type: str,
        adj_type: str = "noadj"
    ) -> None:
        """
        Clear all data for a specific symbol.
        
        Drops the symbol's data table and removes metadata entry.
        
        Args:
            symbol: Symbol identifier
            data_type: 'stock' or 'index'
            adj_type: Adjustment type
        """
        table_name = self._normalize_table_name(symbol, data_type)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Drop the table
            cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
            
            # Delete metadata
            cursor.execute(
                "DELETE FROM metadata WHERE symbol = ? AND data_type = ? AND adj_type = ?",
                (symbol, data_type, adj_type)
            )
            
            conn.commit()
        
        logger.info(f"Cleared data for {symbol} ({data_type}, {adj_type}), dropped table {table_name}")
    
    def get_all_symbols(self, data_type: str = "stock") -> List[str]:
        """
        Get list of all symbols in database.
        
        Args:
            data_type: 'stock' or 'index'
        
        Returns:
            List of symbol identifiers
        """
        query = "SELECT DISTINCT symbol FROM metadata WHERE data_type = ?"
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, (data_type,))
            rows = cursor.fetchall()
        
        return [row[0] for row in rows]
    
    def vacuum(self) -> None:
        """Optimize database by reclaiming unused space."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("VACUUM")
        logger.info("Database vacuumed")
    
    # -----------------------------------------------------------------------
    # CSV Import Methods
    # -----------------------------------------------------------------------
    
    def import_from_csv(
        self,
        csv_path: str,
        symbol: str,
        data_type: str,
        adj_type: str = "noadj"
    ) -> bool:
        """
        Import data from CSV file to database.
        
        Supports old CSV format from cache directory:
        - Stock: ak_SYMBOL_START_END_ADJ.csv with columns: date, open, high, low, close, volume
        - Index: ak_SYMBOL_START_END_ADJ.csv with columns: date, close
        
        Also supports Chinese column names:
        - 日期 (date), 开盘 (open), 收盘 (close), 最高 (high), 最低 (low), 成交量 (volume)
        
        Args:
            csv_path: Path to CSV file
            symbol: Symbol code (e.g., "600519.SH", "000300.SH")
            data_type: 'stock' or 'index'
            adj_type: Adjustment type (noadj, qfq, hfq)
        
        Returns:
            True if import successful, False otherwise
        """
        try:
            import os
            if not os.path.exists(csv_path):
                logger.error(f"CSV file not found: {csv_path}")
                return False
            
            # Read CSV
            df = pd.read_csv(csv_path)
            
            # Map Chinese column names to English
            column_mapping = {
                '日期': 'date',
                'Date': 'date',
                '开盘': 'open',
                'Open': 'open',
                '收盘': 'close',
                'Close': 'close',
                '最高': 'high',
                'High': 'high',
                '最低': 'low',
                'Low': 'low',
                '成交量': 'volume',
                'Volume': 'volume'
            }
            
            # Rename columns
            df.rename(columns=column_mapping, inplace=True)
            
            # Convert date column to datetime and set as index
            if 'date' not in df.columns:
                logger.error(f"No date column found in CSV: {csv_path}")
                return False
            
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            
            if df.empty:
                logger.warning(f"CSV file is empty: {csv_path}")
                return False
            
            # Import based on data type
            if data_type == 'stock':
                # Validate required columns
                required_cols = ['open', 'high', 'low', 'close', 'volume']
                missing_cols = [col for col in required_cols if col not in df.columns]
                if missing_cols:
                    logger.error(f"Missing columns in stock CSV: {missing_cols}")
                    return False
                
                # Select only required columns
                df = df[required_cols]
                self.save_stock_data(symbol, df, adj_type)
                logger.info(f"Imported {len(df)} stock records from {csv_path}")
                
            elif data_type == 'index':
                # Validate required columns
                if 'close' not in df.columns:
                    logger.error(f"Missing 'close' column in index CSV: {csv_path}")
                    return False
                
                # Select only close column
                df = df[['close']]
                self.save_index_data(symbol, df, adj_type)
                logger.info(f"Imported {len(df)} index records from {csv_path}")
            
            else:
                logger.error(f"Invalid data_type: {data_type}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error importing CSV {csv_path}: {e}")
            return False
    
    def batch_import_from_cache(
        self,
        cache_dir: str = "./cache"
    ) -> Dict[str, int]:
        """
        Batch import all CSV files from cache directory.
        
        Automatically detects symbol, date range, and adjustment type from filename.
        Filename pattern: ak_SYMBOL_START_END_ADJ.csv
        
        Args:
            cache_dir: Path to cache directory containing CSV files
        
        Returns:
            Dictionary with import statistics: {
                'success': count,
                'failed': count,
                'skipped': count,
                'files': [list of imported files]
            }
        """
        import os
        import re
        
        stats = {
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'files': []
        }
        
        if not os.path.exists(cache_dir):
            logger.error(f"Cache directory not found: {cache_dir}")
            return stats
        
        # Pattern: ak_SYMBOL_START_END_ADJ.csv
        pattern = re.compile(r'ak_(.+?)_\d{4}-\d{2}-\d{2}_\d{4}-\d{2}-\d{2}_(.+?)\.csv')
        
        for filename in os.listdir(cache_dir):
            if not filename.endswith('.csv'):
                continue
            
            match = pattern.match(filename)
            if not match:
                logger.debug(f"Skipping file with unrecognized pattern: {filename}")
                stats['skipped'] += 1
                continue
            
            symbol = match.group(1)
            adj_type = match.group(2)
            
            # Determine data type based on symbol pattern
            # Stock: 6 digits.SH/SZ (e.g., 600519.SH, 000001.SZ)
            # Index: starts with 0003xx or 3990xx or other index patterns
            if symbol.startswith('0003') or symbol.startswith('3990'):
                data_type = 'index'
            elif re.match(r'^\d{6}\.(SH|SZ)$', symbol):
                data_type = 'stock'
            elif symbol.startswith('^'):
                data_type = 'index'
            else:
                # Default to stock for unknown patterns
                data_type = 'stock'
            
            csv_path = os.path.join(cache_dir, filename)
            
            if self.import_from_csv(csv_path, symbol, data_type, adj_type):
                stats['success'] += 1
                stats['files'].append(filename)
            else:
                stats['failed'] += 1
        
        logger.info(f"Batch import complete: {stats['success']} success, "
                    f"{stats['failed']} failed, {stats['skipped']} skipped")
        
        return stats

