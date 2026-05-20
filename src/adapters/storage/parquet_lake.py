"""Canonical parquet data lake adapter exports."""

from src.platform.data_lake_parquet import (
    ParquetDataLake,
    QualityGate,
    QualityGateResult,
    VersionInfo,
)

__all__ = ["ParquetDataLake", "QualityGate", "QualityGateResult", "VersionInfo"]
