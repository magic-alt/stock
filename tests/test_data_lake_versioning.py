"""
Tests for ParquetDataLake versioning, checksum, and schema gates (B-2).
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
import pytest

from src.platform.data_lake_parquet import ParquetDataLake, VersionInfo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_price_df(seed: int = 0, rows: int = 20) -> pd.DataFrame:
    rng = np.random.RandomState(seed)
    dates = pd.date_range("2024-01-01", periods=rows)
    return pd.DataFrame({
        "open": rng.randint(100, 200, rows).astype(float),
        "high": rng.randint(150, 250, rows).astype(float),
        "low": rng.randint(80, 130, rows).astype(float),
        "close": rng.randint(100, 200, rows).astype(float),
        "volume": rng.randint(1000, 50000, rows).astype(float),
    }, index=dates)


# ---------------------------------------------------------------------------
# Tests: write / read
# ---------------------------------------------------------------------------

class TestParquetDataLake:
    def test_write_creates_parquet_file(self, tmp_path):
        lake = ParquetDataLake(base_dir=str(tmp_path))
        df = _make_price_df(seed=1)
        entry = lake.write_dataset("600519.SH", df, kind="price")

        assert os.path.exists(entry.path)
        assert entry.path.endswith(".parquet")

    def test_read_returns_dataframe(self, tmp_path):
        lake = ParquetDataLake(base_dir=str(tmp_path))
        df = _make_price_df(seed=2)
        lake.write_dataset("600519.SH", df, kind="price")
        result = lake.read_dataset("600519.SH", kind="price")
        assert isinstance(result, pd.DataFrame)

    def test_parquet_roundtrip_data_integrity(self, tmp_path):
        lake = ParquetDataLake(base_dir=str(tmp_path))
        df = _make_price_df(seed=3)
        lake.write_dataset("TEST", df, kind="factor")
        result = lake.read_dataset("TEST", kind="factor")

        pd.testing.assert_frame_equal(df, result, check_dtype=False, check_freq=False)

    def test_read_latest_returns_newest_version(self, tmp_path):
        lake = ParquetDataLake(base_dir=str(tmp_path))
        df1 = _make_price_df(seed=10, rows=10)
        df2 = _make_price_df(seed=20, rows=15)

        lake.write_dataset("ABC", df1, kind="price")  # v1
        lake.write_dataset("ABC", df2, kind="price")  # v2

        result = lake.read_dataset("ABC", kind="price", version="latest")
        assert len(result) == 15  # v2 has 15 rows

    def test_read_specific_version(self, tmp_path):
        lake = ParquetDataLake(base_dir=str(tmp_path))
        df1 = _make_price_df(seed=1, rows=10)
        df2 = _make_price_df(seed=2, rows=20)

        lake.write_dataset("SYM", df1, kind="ohlcv")
        lake.write_dataset("SYM", df2, kind="ohlcv")

        result_v1 = lake.read_dataset("SYM", kind="ohlcv", version=1)
        result_v2 = lake.read_dataset("SYM", kind="ohlcv", version=2)

        assert len(result_v1) == 10
        assert len(result_v2) == 20

    def test_read_missing_symbol_raises(self, tmp_path):
        lake = ParquetDataLake(base_dir=str(tmp_path))
        with pytest.raises(FileNotFoundError):
            lake.read_dataset("NONEXISTENT", kind="price")

    def test_read_missing_version_raises(self, tmp_path):
        lake = ParquetDataLake(base_dir=str(tmp_path))
        df = _make_price_df()
        lake.write_dataset("SYM", df, kind="price")
        with pytest.raises(FileNotFoundError):
            lake.read_dataset("SYM", kind="price", version=99)


# ---------------------------------------------------------------------------
# Tests: list_versions
# ---------------------------------------------------------------------------

class TestListVersions:
    def test_list_versions_empty_initially(self, tmp_path):
        lake = ParquetDataLake(base_dir=str(tmp_path))
        versions = lake.list_versions("NOPE", kind="price")
        assert versions == []

    def test_list_versions_counts_correctly(self, tmp_path):
        lake = ParquetDataLake(base_dir=str(tmp_path))
        df = _make_price_df()
        for _ in range(3):
            lake.write_dataset("X", df, kind="ohlcv")

        versions = lake.list_versions("X", kind="ohlcv")
        assert len(versions) == 3

    def test_list_versions_sorted_ascending(self, tmp_path):
        lake = ParquetDataLake(base_dir=str(tmp_path))
        df = _make_price_df()
        for _ in range(4):
            lake.write_dataset("S", df, kind="price")

        versions = lake.list_versions("S", kind="price")
        nums = [v.version for v in versions]
        assert nums == sorted(nums)

    def test_list_versions_returns_version_info(self, tmp_path):
        lake = ParquetDataLake(base_dir=str(tmp_path))
        df = _make_price_df()
        entry = lake.write_dataset("V", df, kind="factor")
        versions = lake.list_versions("V", kind="factor")
        assert len(versions) == 1
        vi = versions[0]
        assert isinstance(vi, VersionInfo)
        assert vi.version == 1
        assert vi.symbol == "V"
        assert vi.kind == "factor"


# ---------------------------------------------------------------------------
# Tests: auto-incrementing version
# ---------------------------------------------------------------------------

class TestAutoVersioning:
    def test_version_auto_increments(self, tmp_path):
        lake = ParquetDataLake(base_dir=str(tmp_path))
        df = _make_price_df()
        e1 = lake.write_dataset("Z", df, kind="price")
        e2 = lake.write_dataset("Z", df, kind="price")
        e3 = lake.write_dataset("Z", df, kind="price")
        assert e1.version == 1
        assert e2.version == 2
        assert e3.version == 3

    def test_explicit_version_accepted(self, tmp_path):
        lake = ParquetDataLake(base_dir=str(tmp_path))
        df = _make_price_df()
        entry = lake.write_dataset("Q", df, kind="price", version=42)
        assert entry.version == 42


# ---------------------------------------------------------------------------
# Tests: checksum
# ---------------------------------------------------------------------------

class TestChecksum:
    def test_checksum_validation_passes(self, tmp_path):
        lake = ParquetDataLake(base_dir=str(tmp_path))
        df = _make_price_df(seed=5)
        entry = lake.write_dataset("C", df, kind="price")
        assert lake.validate_checksum(entry.entry_id) is True

    def test_tampered_file_fails_checksum(self, tmp_path):
        lake = ParquetDataLake(base_dir=str(tmp_path))
        df = _make_price_df(seed=6)
        entry = lake.write_dataset("T", df, kind="price")

        # Corrupt the file
        with open(entry.path, "ab") as fh:
            fh.write(b"\x00\x01\x02\x03")

        assert lake.validate_checksum(entry.entry_id) is False

    def test_missing_file_fails_checksum(self, tmp_path):
        lake = ParquetDataLake(base_dir=str(tmp_path))
        df = _make_price_df(seed=7)
        entry = lake.write_dataset("M", df, kind="price")
        os.remove(entry.path)
        assert lake.validate_checksum(entry.entry_id) is False

    def test_unknown_entry_id_fails_checksum(self, tmp_path):
        lake = ParquetDataLake(base_dir=str(tmp_path))
        assert lake.validate_checksum("nonexistent-id") is False

    def test_checksum_stored_in_entry(self, tmp_path):
        lake = ParquetDataLake(base_dir=str(tmp_path))
        df = _make_price_df()
        entry = lake.write_dataset("CS", df, kind="price")
        assert len(entry.checksum) == 64  # SHA-256 hex digest


# ---------------------------------------------------------------------------
# Tests: schema
# ---------------------------------------------------------------------------

class TestSchema:
    def test_schema_persisted_in_manifest(self, tmp_path):
        lake = ParquetDataLake(base_dir=str(tmp_path))
        df = _make_price_df()
        entry = lake.write_dataset("SC", df, kind="price")
        assert "close" in entry.schema
        assert "volume" in entry.schema

    def test_schema_reflects_dtypes(self, tmp_path):
        lake = ParquetDataLake(base_dir=str(tmp_path))
        df = pd.DataFrame({"a": [1, 2], "b": [1.0, 2.0]})
        entry = lake.write_dataset("DT", df, kind="test")
        assert isinstance(entry.schema["a"], str)  # dtype name stored as string


# ---------------------------------------------------------------------------
# Tests: production promotion
# ---------------------------------------------------------------------------

class TestProductionPromotion:
    def test_is_production_false_by_default(self, tmp_path):
        lake = ParquetDataLake(base_dir=str(tmp_path))
        df = _make_price_df()
        entry = lake.write_dataset("PP", df, kind="price")
        assert entry.is_production is False

    def test_promote_to_production(self, tmp_path):
        lake = ParquetDataLake(base_dir=str(tmp_path))
        df = _make_price_df()
        entry = lake.write_dataset("PP2", df, kind="price")
        lake.promote_to_production(entry.entry_id)

        # Re-fetch from registry to verify persistence
        updated = lake._registry.get(entry.entry_id)
        assert updated is not None
        assert updated.is_production is True

    def test_promote_unknown_entry_raises(self, tmp_path):
        lake = ParquetDataLake(base_dir=str(tmp_path))
        with pytest.raises(ValueError, match="not found"):
            lake.promote_to_production("does-not-exist")

    def test_promote_tampered_file_raises(self, tmp_path):
        lake = ParquetDataLake(base_dir=str(tmp_path))
        df = _make_price_df()
        entry = lake.write_dataset("TAM", df, kind="price")
        with open(entry.path, "ab") as fh:
            fh.write(b"\xff\xfe")
        with pytest.raises(ValueError, match="Checksum"):
            lake.promote_to_production(entry.entry_id)
