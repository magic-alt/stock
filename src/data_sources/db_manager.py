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
    
    Schema:
        stock_daily: symbol, date, open, high, low, close, volume, adj_type
        index_daily: symbol, date, close, adj_type
        metadata: symbol, data_type, first_date, last_date, last_update
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
        """Create database tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Stock daily data table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stock_daily (
                    symbol TEXT NOT NULL,
                    date TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume REAL,
                    adj_type TEXT,
                    PRIMARY KEY (symbol, date, adj_type)
                )
            """)
            
            # Index daily data table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS index_daily (
                    symbol TEXT NOT NULL,
                    date TEXT NOT NULL,
                    close REAL,
                    adj_type TEXT,
                    PRIMARY KEY (symbol, date, adj_type)
                )
            """)
            
            # Metadata table for tracking data ranges
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metadata (
                    symbol TEXT NOT NULL,
                    data_type TEXT NOT NULL,
                    adj_type TEXT NOT NULL,
                    first_date TEXT,
                    last_date TEXT,
                    last_update TEXT,
                    PRIMARY KEY (symbol, data_type, adj_type)
                )
            """)
            
            # Create indexes for faster queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_stock_symbol_date 
                ON stock_daily (symbol, date)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_index_symbol_date 
                ON index_daily (symbol, date)
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
            symbol: Stock symbol
            df: DataFrame with date index and OHLCV columns
            adj_type: Adjustment type (noadj, qfq, hfq)
        """
        if df.empty:
            return
        
        # Prepare data
        df = df.copy()
        df['symbol'] = symbol
        df['adj_type'] = adj_type
        df['date'] = df.index.strftime('%Y-%m-%d')
        
        # Required columns
        columns = ['symbol', 'date', 'open', 'high', 'low', 'close', 'volume', 'adj_type']
        
        with sqlite3.connect(self.db_path) as conn:
            # Insert or replace data
            df[columns].to_sql(
                'stock_daily',
                conn,
                if_exists='append',
                index=False,
                method='multi'
            )
            
            # Remove duplicates (keep latest)
            conn.execute("""
                DELETE FROM stock_daily
                WHERE rowid NOT IN (
                    SELECT MAX(rowid)
                    FROM stock_daily
                    GROUP BY symbol, date, adj_type
                )
            """)
            
            # Update metadata
            self._update_metadata(
                conn, symbol, 'stock', adj_type,
                df.index.min(), df.index.max()
            )
            
            conn.commit()
        
        logger.debug(f"Saved {len(df)} rows for {symbol} ({adj_type})")
    
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
        query = """
            SELECT date, open, high, low, close, volume
            FROM stock_daily
            WHERE symbol = ? AND adj_type = ?
              AND date >= ? AND date <= ?
            ORDER BY date
        """
        
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(
                query,
                conn,
                params=(symbol, adj_type, start, end)
            )
        
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
        
        Args:
            symbol: Index symbol
            df: DataFrame with date index and close column
            adj_type: Adjustment type
        """
        if df.empty:
            return
        
        # Prepare data
        df = df.copy()
        df['symbol'] = symbol
        df['adj_type'] = adj_type
        df['date'] = df.index.strftime('%Y-%m-%d')
        
        # Required columns
        columns = ['symbol', 'date', 'close', 'adj_type']
        
        with sqlite3.connect(self.db_path) as conn:
            # Insert or replace data
            df[columns].to_sql(
                'index_daily',
                conn,
                if_exists='append',
                index=False,
                method='multi'
            )
            
            # Remove duplicates
            conn.execute("""
                DELETE FROM index_daily
                WHERE rowid NOT IN (
                    SELECT MAX(rowid)
                    FROM index_daily
                    GROUP BY symbol, date, adj_type
                )
            """)
            
            # Update metadata
            self._update_metadata(
                conn, symbol, 'index', adj_type,
                df.index.min(), df.index.max()
            )
            
            conn.commit()
        
        logger.debug(f"Saved {len(df)} rows for index {symbol} ({adj_type})")
    
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
        query = """
            SELECT date, close
            FROM index_daily
            WHERE symbol = ? AND adj_type = ?
              AND date >= ? AND date <= ?
            ORDER BY date
        """
        
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(
                query,
                conn,
                params=(symbol, adj_type, start, end)
            )
        
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
        first_date: datetime,
        last_date: datetime
    ) -> None:
        """Update metadata table with data range information."""
        cursor = conn.cursor()
        
        # Check if metadata exists
        cursor.execute("""
            SELECT first_date, last_date
            FROM metadata
            WHERE symbol = ? AND data_type = ? AND adj_type = ?
        """, (symbol, data_type, adj_type))
        
        row = cursor.fetchone()
        
        if row:
            # Update existing metadata
            existing_first = datetime.strptime(row[0], '%Y-%m-%d')
            existing_last = datetime.strptime(row[1], '%Y-%m-%d')
            
            new_first = min(first_date, existing_first)
            new_last = max(last_date, existing_last)
            
            cursor.execute("""
                UPDATE metadata
                SET first_date = ?, last_date = ?, last_update = ?
                WHERE symbol = ? AND data_type = ? AND adj_type = ?
            """, (
                new_first.strftime('%Y-%m-%d'),
                new_last.strftime('%Y-%m-%d'),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                symbol, data_type, adj_type
            ))
        else:
            # Insert new metadata
            cursor.execute("""
                INSERT INTO metadata (symbol, data_type, adj_type, first_date, last_date, last_update)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                symbol, data_type, adj_type,
                first_date.strftime('%Y-%m-%d'),
                last_date.strftime('%Y-%m-%d'),
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
            Tuple of (first_date, last_date) or None if no data
        """
        query = """
            SELECT first_date, last_date
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
        
        Args:
            symbol: Symbol identifier
            data_type: 'stock' or 'index'
            adj_type: Adjustment type
        """
        table_name = f"{data_type}_daily"
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Delete data
            cursor.execute(
                f"DELETE FROM {table_name} WHERE symbol = ? AND adj_type = ?",
                (symbol, adj_type)
            )
            
            # Delete metadata
            cursor.execute(
                "DELETE FROM metadata WHERE symbol = ? AND data_type = ? AND adj_type = ?",
                (symbol, data_type, adj_type)
            )
            
            conn.commit()
        
        logger.info(f"Cleared data for {symbol} ({data_type}, {adj_type})")
    
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
