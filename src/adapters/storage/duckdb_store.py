"""Compatibility alias for the canonical DuckDB storage adapter."""

from __future__ import annotations

from src.adapters.storage.duckdb import DuckDBConfig, DuckDBTimeSeriesStore

__all__ = ["DuckDBConfig", "DuckDBTimeSeriesStore"]
