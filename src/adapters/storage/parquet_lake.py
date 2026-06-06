"""Canonical parquet data lake adapter exports."""

from __future__ import annotations

from src.platform.data_lake_parquet import (
    ParquetDataLake,
    QualityGate,
    QualityGateResult,
    VersionInfo,
)

__all__ = ["ParquetDataLake", "QualityGate", "QualityGateResult", "VersionInfo"]
