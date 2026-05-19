"""
Parquet-backed Data Lake with versioning and checksum gates.

Extends the base DataLake with:
- Parquet file storage (via pandas/pyarrow)
- Auto-incrementing version numbers per (symbol, kind)
- SHA-256 checksum integrity validation
- Schema capture from DataFrame dtypes
- Hot/cold tiered storage layout
- Production promotion gate
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd

from src.platform.data_lake import DataLake, DataLakeEntry


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class VersionInfo:
    """Summary of a single dataset version."""
    entry_id: str
    symbol: str
    kind: str
    version: int
    checksum: str
    schema: Dict[str, Any]
    is_production: bool
    created_at: str
    path: str
    tier: str = "hot"


@dataclass
class QualityGateResult:
    """Result of validating a dataset before production promotion."""
    passed: bool
    checks: Dict[str, bool]
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class QualityGate:
    """Data quality gate for production data lake promotion."""

    def __init__(
        self,
        *,
        required_columns: Optional[List[str]] = None,
        max_missing_ratio: float = 0.05,
        require_monotonic_index: bool = True,
        enforce_ohlc: bool = False,
    ) -> None:
        self.required_columns = required_columns or []
        self.max_missing_ratio = max_missing_ratio
        self.require_monotonic_index = require_monotonic_index
        self.enforce_ohlc = enforce_ohlc

    def validate(
        self,
        df: pd.DataFrame,
        *,
        expected_schema: Optional[Dict[str, Any]] = None,
    ) -> QualityGateResult:
        checks: Dict[str, bool] = {}
        errors: List[str] = []
        warnings: List[str] = []
        total_cells = int(df.shape[0] * df.shape[1]) if df is not None else 0
        missing_cells = int(df.isna().sum().sum()) if total_cells else 0
        missing_ratio = float(missing_cells / total_cells) if total_cells else 0.0
        metrics = {
            "rows": int(len(df)),
            "columns": int(len(df.columns)),
            "missing_cells": missing_cells,
            "missing_ratio": missing_ratio,
            "duplicate_index_count": int(df.index.duplicated().sum()),
        }

        checks["non_empty"] = len(df) > 0 and len(df.columns) > 0
        if not checks["non_empty"]:
            errors.append("dataset is empty")

        missing_required = [col for col in self.required_columns if col not in df.columns]
        checks["required_columns"] = not missing_required
        if missing_required:
            errors.append(f"missing required columns: {', '.join(missing_required)}")

        checks["missing_ratio"] = missing_ratio <= self.max_missing_ratio
        if not checks["missing_ratio"]:
            errors.append(
                f"missing ratio {missing_ratio:.4f} exceeds threshold {self.max_missing_ratio:.4f}"
            )

        checks["unique_index"] = metrics["duplicate_index_count"] == 0
        if not checks["unique_index"]:
            errors.append("index contains duplicate labels")

        if self.require_monotonic_index:
            checks["monotonic_index"] = bool(df.index.is_monotonic_increasing)
            if not checks["monotonic_index"]:
                errors.append("index is not monotonic increasing")

        if expected_schema:
            actual_schema = {col: str(dtype) for col, dtype in df.dtypes.items()}
            missing_schema_cols = [col for col in expected_schema if col not in actual_schema]
            type_mismatches = [
                col
                for col, dtype in expected_schema.items()
                if col in actual_schema and str(dtype) != actual_schema[col]
            ]
            checks["schema"] = not missing_schema_cols and not type_mismatches
            if missing_schema_cols:
                errors.append(f"schema columns missing from dataset: {', '.join(missing_schema_cols)}")
            if type_mismatches:
                warnings.append(f"schema dtype drift detected: {', '.join(type_mismatches)}")

        if self.enforce_ohlc and all(col in df.columns for col in ["open", "high", "low", "close"]):
            high_floor = df[["open", "low", "close"]].max(axis=1)
            low_ceiling = df[["open", "high", "close"]].min(axis=1)
            ohlc_ok = bool(((df["high"] >= high_floor) & (df["low"] <= low_ceiling)).all())
            checks["ohlc_bounds"] = ohlc_ok
            if not ohlc_ok:
                errors.append("OHLC bounds are invalid")
            if "volume" in df.columns:
                volume_ok = bool((df["volume"] >= 0).all())
                checks["non_negative_volume"] = volume_ok
                if not volume_ok:
                    errors.append("volume contains negative values")
        elif self.enforce_ohlc:
            checks["ohlc_bounds"] = False
            errors.append("OHLC validation requires open/high/low/close columns")

        return QualityGateResult(
            passed=not errors,
            checks=checks,
            errors=errors,
            warnings=warnings,
            metrics=metrics,
        )


class ParquetDataLake:
    """
    Parquet-backed data lake with versioning and checksum gates.

    Layout::

        {base_dir}/{tier}/{kind}/{symbol}/v{version}.parquet

    The manifest is maintained by the parent :class:`DataLake` registry.

    Usage::

        lake = ParquetDataLake(base_dir="./data_lake")
        entry = lake.write_dataset("600519.SH", df, kind="price")
        df2   = lake.read_dataset("600519.SH", kind="price")
        ok    = lake.validate_checksum(entry.entry_id)
        lake.promote_to_production(entry.entry_id)
    """

    def __init__(self, base_dir: str = "./data_lake") -> None:
        self.base_dir = base_dir
        self._registry = DataLake(base_dir=base_dir)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def write_dataset(
        self,
        symbol: str,
        df: pd.DataFrame,
        kind: str,
        version: Optional[int] = None,
        tier: str = "hot",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DataLakeEntry:
        """
        Serialize *df* to Parquet and register in the manifest.

        Args:
            symbol: Trading symbol identifier (e.g. ``"600519.SH"``).
            df:     DataFrame to persist.
            kind:   Dataset category key (e.g. ``"price"``, ``"factor"``).
            version: Explicit version number; if ``None``, auto-increments
                     from the highest existing version for this (symbol, kind).
            tier: Storage tier, one of ``"hot"``, ``"cold"`` or ``"archive"``.
            metadata: Optional metadata merged into the manifest entry.

        Returns:
            :class:`DataLakeEntry` with ``version``, ``checksum``, ``schema``
            and ``is_production = False`` populated.
        """
        if version is None:
            existing = self.list_versions(symbol, kind)
            version = (max(v.version for v in existing) + 1) if existing else 1
        tier = self._normalize_tier(tier)

        # Build target path
        dir_path = os.path.join(self.base_dir, tier, kind, symbol)
        os.makedirs(dir_path, exist_ok=True)
        file_path = os.path.join(dir_path, f"v{version}.parquet")

        # Serialise to bytes
        buf = io.BytesIO()
        df.to_parquet(buf, index=True, engine="auto")
        parquet_bytes = buf.getvalue()

        # Write to disk
        with open(file_path, "wb") as fh:
            fh.write(parquet_bytes)

        # Compute checksum
        checksum = hashlib.sha256(parquet_bytes).hexdigest()

        # Capture schema
        schema = {col: str(dtype) for col, dtype in df.dtypes.items()}

        # Register in base DataLake (file path exists now)
        entry_metadata = dict(metadata or {})
        entry_metadata.update({"symbol": symbol, "tier": tier})

        entry = DataLakeEntry(
            entry_id=str(uuid.uuid4()),
            kind=kind,
            name=self._make_name(symbol, kind, version),
            path=file_path,
            version=version,
            checksum=checksum,
            schema=schema,
            is_production=False,
            metadata=entry_metadata,
        )
        self._registry._entries[entry.entry_id] = entry
        self._registry._save()
        return entry

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def read_dataset(
        self,
        symbol: str,
        kind: str,
        version: "int | str" = "latest",
        tier: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Read a dataset from Parquet.

        Args:
            symbol:  Dataset symbol.
            kind:    Dataset kind.
            version: Explicit version int or ``"latest"`` (default).
            tier: Optional storage tier filter.

        Returns:
            Pandas DataFrame.

        Raises:
            FileNotFoundError: if no matching version exists.
        """
        versions = self.list_versions(symbol, kind, tier=tier)
        if not versions:
            raise FileNotFoundError(f"No dataset found for {symbol}/{kind}")

        if version == "latest":
            target = max(versions, key=lambda v: v.version)
        else:
            targets = [v for v in versions if v.version == int(version)]
            if not targets:
                raise FileNotFoundError(
                    f"Version {version} not found for {symbol}/{kind}"
                )
            target = targets[0]

        return pd.read_parquet(target.path)

    # ------------------------------------------------------------------
    # Version listing
    # ------------------------------------------------------------------

    def list_versions(self, symbol: str, kind: str, tier: Optional[str] = None) -> List[VersionInfo]:
        """Return all recorded versions for (symbol, kind), sorted ascending."""
        tier_filter = self._normalize_tier(tier) if tier is not None else None
        results: List[VersionInfo] = []
        for entry in self._registry.list(kind=kind):
            entry_tier = entry.metadata.get("tier", "hot")
            if entry.metadata.get("symbol") == symbol and (tier_filter is None or entry_tier == tier_filter):
                results.append(
                    VersionInfo(
                        entry_id=entry.entry_id,
                        symbol=symbol,
                        kind=kind,
                        version=entry.version,
                        checksum=entry.checksum,
                        schema=entry.schema,
                        is_production=entry.is_production,
                        created_at=entry.created_at,
                        path=entry.path,
                        tier=entry_tier,
                    )
                )
        return sorted(results, key=lambda v: v.version)

    # ------------------------------------------------------------------
    # Checksum validation
    # ------------------------------------------------------------------

    def validate_checksum(self, entry_id: str) -> bool:
        """
        Re-compute SHA-256 of the on-disk Parquet file and compare to manifest.

        Returns:
            ``True`` if checksums match, ``False`` if file is missing or tampered.
        """
        entry = self._registry.get(entry_id)
        if entry is None:
            return False
        if not os.path.exists(entry.path):
            return False
        with open(entry.path, "rb") as fh:
            actual = hashlib.sha256(fh.read()).hexdigest()
        return actual == entry.checksum

    # ------------------------------------------------------------------
    # Production promotion
    # ------------------------------------------------------------------

    def validate_quality(
        self,
        entry_id: str,
        quality_gate: Optional[QualityGate] = None,
    ) -> QualityGateResult:
        """Validate a data lake entry against the configured production gate."""
        entry = self._registry.get(entry_id)
        if entry is None:
            raise ValueError(f"Entry {entry_id!r} not found")
        if not self.validate_checksum(entry_id):
            return QualityGateResult(
                passed=False,
                checks={"checksum": False},
                errors=[f"Checksum validation failed for {entry_id!r}"],
            )
        df = pd.read_parquet(entry.path)
        gate = quality_gate or self._default_quality_gate(entry)
        result = gate.validate(df, expected_schema=entry.schema)
        result.checks = {"checksum": True, **result.checks}
        entry.metadata["quality_gate"] = result.to_dict()
        self._registry._save()
        return result

    def promote_to_production(
        self,
        entry_id: str,
        quality_gate: Optional[QualityGate] = None,
    ) -> QualityGateResult:
        """
        Mark entry as production-ready (checksum and quality gate must pass first).

        Raises:
            ValueError: if entry not found, checksum fails, or the quality gate fails.
        """
        entry = self._registry.get(entry_id)
        if entry is None:
            raise ValueError(f"Entry {entry_id!r} not found")
        result = self.validate_quality(entry_id, quality_gate=quality_gate)
        if not result.passed:
            raise ValueError(f"Quality gate failed for {entry_id!r}: {'; '.join(result.errors)}")
        entry.is_production = True
        self._registry._save()
        return result

    def move_to_tier(self, entry_id: str, tier: str) -> DataLakeEntry:
        """Move a dataset file to another storage tier and update the manifest."""
        target_tier = self._normalize_tier(tier)
        entry = self._registry.get(entry_id)
        if entry is None:
            raise ValueError(f"Entry {entry_id!r} not found")
        symbol = entry.metadata.get("symbol")
        if not symbol:
            raise ValueError(f"Entry {entry_id!r} has no symbol metadata")
        if not os.path.exists(entry.path):
            raise FileNotFoundError(entry.path)

        target_dir = os.path.join(self.base_dir, target_tier, entry.kind, symbol)
        os.makedirs(target_dir, exist_ok=True)
        target_path = os.path.join(target_dir, os.path.basename(entry.path))
        if os.path.abspath(entry.path) != os.path.abspath(target_path):
            os.replace(entry.path, target_path)
        entry.path = target_path
        entry.metadata["tier"] = target_tier
        self._registry._save()
        return entry

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_name(symbol: str, kind: str, version: int) -> str:
        return f"{symbol}/{kind}/v{version}"

    @staticmethod
    def _normalize_tier(tier: Optional[str]) -> str:
        value = (tier or "hot").lower()
        if value not in {"hot", "cold", "archive"}:
            raise ValueError("tier must be one of: hot, cold, archive")
        return value

    @staticmethod
    def _default_quality_gate(entry: DataLakeEntry) -> QualityGate:
        price_kinds = {"price", "prices", "ohlcv", "bar", "bars", "daily"}
        is_price_like = entry.kind.lower() in price_kinds
        return QualityGate(
            required_columns=["open", "high", "low", "close"] if is_price_like else [],
            enforce_ohlc=is_price_like,
        )


__all__ = ["ParquetDataLake", "QualityGate", "QualityGateResult", "VersionInfo"]
