"""Compatibility alias for the canonical DuckDB storage adapter."""

from src.adapters.storage.duckdb import DuckDBConfig, DuckDBTimeSeriesStore

__all__ = ["DuckDBConfig", "DuckDBTimeSeriesStore"]
