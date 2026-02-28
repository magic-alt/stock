"""
DuckDB Time Series Storage Engine (V5.0-B-2).

Provides a high-performance columnar storage backend for market data,
replacing SQLite for OHLCV queries. Zero-configuration embedded database.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional, Sequence

import pandas as pd

from src.core.logger import get_logger

logger = get_logger("data.duckdb_store")

try:
    import duckdb
except ImportError:
    duckdb = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Schema & configuration
# ---------------------------------------------------------------------------

@dataclass
class DuckDBConfig:
    """Configuration for the DuckDB time series store."""
    db_path: str = ":memory:"
    read_only: bool = False
    threads: int = 0  # 0 = auto
    memory_limit: str = ""  # e.g. "2GB", empty = unlimited


# ---------------------------------------------------------------------------
# Core store
# ---------------------------------------------------------------------------

class DuckDBTimeSeriesStore:
    """Embedded columnar time-series store backed by DuckDB.

    Features:
    - Zero-config embedded operation (single file or in-memory)
    - Columnar storage with automatic compression
    - Bulk ingest from DataFrame / Parquet
    - SQL-based query interface
    - Frequency-aware aggregation (tick → minute → daily)
    - Parquet import/export
    """

    DDL = """
    CREATE TABLE IF NOT EXISTS ohlcv (
        symbol   VARCHAR NOT NULL,
        ts       TIMESTAMP NOT NULL,
        freq     VARCHAR NOT NULL DEFAULT 'daily',
        open     DOUBLE,
        high     DOUBLE,
        low      DOUBLE,
        close    DOUBLE,
        volume   DOUBLE DEFAULT 0,
        amount   DOUBLE DEFAULT 0,
        PRIMARY KEY (symbol, ts, freq)
    );
    CREATE INDEX IF NOT EXISTS idx_ohlcv_sym_ts ON ohlcv (symbol, ts);
    """

    def __init__(self, config: Optional[DuckDBConfig] = None) -> None:
        if duckdb is None:
            raise ImportError("duckdb is required: pip install duckdb")
        self.config = config or DuckDBConfig()
        self._conn: Optional[duckdb.DuckDBPyConnection] = None
        self._ensure_connection()
        self._ensure_schema()

    def _ensure_connection(self) -> None:
        if self._conn is not None:
            return
        kwargs: Dict[str, Any] = {"read_only": self.config.read_only}
        if self.config.threads > 0:
            kwargs["config"] = {"threads": str(self.config.threads)}
        if self.config.memory_limit:
            kwargs.setdefault("config", {})["memory_limit"] = self.config.memory_limit
        self._conn = duckdb.connect(self.config.db_path, **kwargs)

    def _ensure_schema(self) -> None:
        assert self._conn is not None
        for stmt in self.DDL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                self._conn.execute(stmt)

    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        self._ensure_connection()
        assert self._conn is not None
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # Ingest
    # ------------------------------------------------------------------

    def ingest(
        self,
        symbol: str,
        df: pd.DataFrame,
        freq: str = "daily",
        *,
        replace: bool = True,
    ) -> int:
        """Ingest a DataFrame of OHLCV data.

        Args:
            symbol: Instrument symbol (e.g. '600519.SH').
            df: DataFrame with columns [open, high, low, close, volume] and
                a DatetimeIndex (or a 'date'/'ts' column).
            freq: Data frequency label ('daily', '1min', '5min', 'tick', ...).
            replace: If True, delete existing data for this symbol+freq first.

        Returns:
            Number of rows ingested.
        """
        if df.empty:
            return 0

        # Normalise index → 'ts' column
        work = df.copy()
        if "ts" not in work.columns:
            if "date" in work.columns:
                work = work.rename(columns={"date": "ts"})
            elif isinstance(work.index, pd.DatetimeIndex):
                work = work.reset_index()
                idx_col = work.columns[0]
                work = work.rename(columns={idx_col: "ts"})
            else:
                raise ValueError("DataFrame must have a DatetimeIndex or a 'ts'/'date' column")

        work["ts"] = pd.to_datetime(work["ts"])
        work["symbol"] = symbol
        work["freq"] = freq

        # Ensure columns exist
        for col in ("open", "high", "low", "close"):
            if col not in work.columns:
                work[col] = 0.0
        if "volume" not in work.columns:
            work["volume"] = 0.0
        if "amount" not in work.columns:
            work["amount"] = 0.0

        cols = ["symbol", "ts", "freq", "open", "high", "low", "close", "volume", "amount"]
        work = work[cols]

        if replace:
            self.conn.execute(
                "DELETE FROM ohlcv WHERE symbol = ? AND freq = ?",
                [symbol, freq],
            )

        # Use DuckDB's register → INSERT from registered DataFrame
        self.conn.register("_ingest_df", work)
        self.conn.execute("INSERT INTO ohlcv SELECT * FROM _ingest_df")
        self.conn.unregister("_ingest_df")

        rows = len(work)
        logger.info("duckdb_ingest", symbol=symbol, freq=freq, rows=rows)
        return rows

    def ingest_parquet(self, path: str, symbol: str, freq: str = "daily") -> int:
        """Ingest data from a Parquet file."""
        df = pd.read_parquet(path)
        return self.ingest(symbol, df, freq=freq)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query(
        self,
        symbol: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        freq: str = "daily",
        columns: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """Query OHLCV data for a single symbol.

        Args:
            symbol: Instrument symbol.
            start: Start date (inclusive), e.g. '2024-01-01'.
            end: End date (inclusive), e.g. '2024-12-31'.
            freq: Frequency filter.
            columns: Specific columns to select (default: all OHLCV).

        Returns:
            DataFrame indexed by timestamp.
        """
        col_str = ", ".join(columns) if columns else "ts, open, high, low, close, volume, amount"
        if "ts" not in (columns or []) and columns:
            col_str = "ts, " + col_str

        sql = f"SELECT {col_str} FROM ohlcv WHERE symbol = ? AND freq = ?"
        params: list = [symbol, freq]

        if start:
            sql += " AND ts >= ?"
            params.append(start)
        if end:
            sql += " AND ts <= ?"
            params.append(end)

        sql += " ORDER BY ts"
        result = self.conn.execute(sql, params).fetchdf()
        if not result.empty and "ts" in result.columns:
            result = result.set_index("ts")
            result.index.name = None
        return result

    def query_multiple(
        self,
        symbols: Sequence[str],
        start: Optional[str] = None,
        end: Optional[str] = None,
        freq: str = "daily",
    ) -> Dict[str, pd.DataFrame]:
        """Query OHLCV data for multiple symbols."""
        return {s: self.query(s, start, end, freq) for s in symbols}

    def list_symbols(self, freq: Optional[str] = None) -> List[str]:
        """List all symbols in the store."""
        if freq:
            result = self.conn.execute(
                "SELECT DISTINCT symbol FROM ohlcv WHERE freq = ? ORDER BY symbol",
                [freq],
            ).fetchall()
        else:
            result = self.conn.execute(
                "SELECT DISTINCT symbol FROM ohlcv ORDER BY symbol"
            ).fetchall()
        return [r[0] for r in result]

    def count(self, symbol: Optional[str] = None, freq: Optional[str] = None) -> int:
        """Count rows in the store."""
        sql = "SELECT COUNT(*) FROM ohlcv"
        params: list = []
        clauses = []
        if symbol:
            clauses.append("symbol = ?")
            params.append(symbol)
        if freq:
            clauses.append("freq = ?")
            params.append(freq)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        return int(self.conn.execute(sql, params).fetchone()[0])

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------

    def aggregate(
        self,
        symbol: str,
        from_freq: str,
        to_freq: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> pd.DataFrame:
        """Aggregate from a higher frequency to a lower frequency.

        Supported: '1min' → '5min', '1min' → 'daily', etc.
        Uses DuckDB's time_bucket for grouping.
        """
        bucket_map = {
            "1min": "INTERVAL '1 minute'",
            "5min": "INTERVAL '5 minutes'",
            "15min": "INTERVAL '15 minutes'",
            "30min": "INTERVAL '30 minutes'",
            "60min": "INTERVAL '1 hour'",
            "daily": "INTERVAL '1 day'",
        }
        bucket = bucket_map.get(to_freq)
        if not bucket:
            raise ValueError(f"Unsupported target frequency: {to_freq}")

        sql = f"""
        SELECT
            time_bucket({bucket}, ts) AS ts,
            FIRST(open) AS open,
            MAX(high) AS high,
            MIN(low) AS low,
            LAST(close) AS close,
            SUM(volume) AS volume,
            SUM(amount) AS amount
        FROM ohlcv
        WHERE symbol = ? AND freq = ?
        """
        params: list = [symbol, from_freq]
        if start:
            sql += " AND ts >= ?"
            params.append(start)
        if end:
            sql += " AND ts <= ?"
            params.append(end)
        sql += " GROUP BY time_bucket({bucket}, ts) ORDER BY ts".format(bucket=bucket)

        result = self.conn.execute(sql, params).fetchdf()
        if not result.empty:
            result = result.set_index("ts")
            result.index.name = None
        return result

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def delete(self, symbol: str, freq: Optional[str] = None) -> int:
        """Delete data for a symbol (optionally filtered by frequency)."""
        if freq:
            result = self.conn.execute(
                "DELETE FROM ohlcv WHERE symbol = ? AND freq = ?",
                [symbol, freq],
            )
        else:
            result = self.conn.execute(
                "DELETE FROM ohlcv WHERE symbol = ?",
                [symbol],
            )
        return result.fetchone()[0] if result.description else 0

    def export_parquet(self, path: str, symbol: Optional[str] = None, freq: Optional[str] = None) -> str:
        """Export data to Parquet file."""
        sql = "SELECT * FROM ohlcv"
        params: list = []
        clauses = []
        if symbol:
            clauses.append("symbol = ?")
            params.append(symbol)
        if freq:
            clauses.append("freq = ?")
            params.append(freq)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)

        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.conn.execute(
            f"COPY ({sql}) TO '{path}' (FORMAT PARQUET, COMPRESSION ZSTD)",
            params,
        )
        logger.info("duckdb_export", path=path)
        return path

    def vacuum(self) -> None:
        """Reclaim space and optimize storage."""
        self.conn.execute("CHECKPOINT")

    def stats(self) -> Dict[str, Any]:
        """Return store statistics."""
        total = self.count()
        symbols = self.list_symbols()
        freqs = [r[0] for r in self.conn.execute(
            "SELECT DISTINCT freq FROM ohlcv ORDER BY freq"
        ).fetchall()]
        return {
            "total_rows": total,
            "symbols": len(symbols),
            "frequencies": freqs,
            "db_path": self.config.db_path,
        }
