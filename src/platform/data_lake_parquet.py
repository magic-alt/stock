"""
Parquet-backed Data Lake with versioning and checksum gates.

Extends the base DataLake with:
- Parquet file storage (via pandas/pyarrow)
- Auto-incrementing version numbers per (symbol, kind)
- SHA-256 checksum integrity validation
- Schema capture from DataFrame dtypes
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


class ParquetDataLake:
    """
    Parquet-backed data lake with versioning and checksum gates.

    Layout::

        {base_dir}/{kind}/{symbol}/v{version}.parquet

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
    ) -> DataLakeEntry:
        """
        Serialize *df* to Parquet and register in the manifest.

        Args:
            symbol: Trading symbol identifier (e.g. ``"600519.SH"``).
            df:     DataFrame to persist.
            kind:   Dataset category key (e.g. ``"price"``, ``"factor"``).
            version: Explicit version number; if ``None``, auto-increments
                     from the highest existing version for this (symbol, kind).

        Returns:
            :class:`DataLakeEntry` with ``version``, ``checksum``, ``schema``
            and ``is_production = False`` populated.
        """
        if version is None:
            existing = self.list_versions(symbol, kind)
            version = (max(v.version for v in existing) + 1) if existing else 1

        # Build target path
        dir_path = os.path.join(self.base_dir, kind, symbol)
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
        entry = DataLakeEntry(
            entry_id=str(uuid.uuid4()),
            kind=kind,
            name=self._make_name(symbol, kind, version),
            path=file_path,
            version=version,
            checksum=checksum,
            schema=schema,
            is_production=False,
            metadata={"symbol": symbol},
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
    ) -> pd.DataFrame:
        """
        Read a dataset from Parquet.

        Args:
            symbol:  Dataset symbol.
            kind:    Dataset kind.
            version: Explicit version int or ``"latest"`` (default).

        Returns:
            Pandas DataFrame.

        Raises:
            FileNotFoundError: if no matching version exists.
        """
        versions = self.list_versions(symbol, kind)
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

    def list_versions(self, symbol: str, kind: str) -> List[VersionInfo]:
        """Return all recorded versions for (symbol, kind), sorted ascending."""
        results: List[VersionInfo] = []
        for entry in self._registry.list(kind=kind):
            if entry.metadata.get("symbol") == symbol:
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

    def promote_to_production(self, entry_id: str) -> None:
        """
        Mark entry as production-ready (checksum must pass first).

        Raises:
            ValueError: if entry not found or checksum fails.
        """
        entry = self._registry.get(entry_id)
        if entry is None:
            raise ValueError(f"Entry {entry_id!r} not found")
        if not self.validate_checksum(entry_id):
            raise ValueError(
                f"Checksum validation failed for {entry_id!r}; cannot promote"
            )
        entry.is_production = True
        self._registry._save()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_name(symbol: str, kind: str, version: int) -> str:
        return f"{symbol}/{kind}/v{version}"


__all__ = ["ParquetDataLake", "VersionInfo"]
