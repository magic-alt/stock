import os
import sqlite3
import tempfile
import gc

from src.data_sources.db_manager import SQLiteDataManager


def test_lineage_recording():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = os.path.join(tmpdir, "market_data.db")
        db = SQLiteDataManager(db_path)
        db.record_lineage(
            symbol="AAA",
            data_type="stock",
            adj_type="noadj",
            source="test",
            start_date="2024-01-01",
            end_date="2024-01-02",
            record_count=2,
            checksum="abc123",
        )

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT symbol, source, record_count FROM lineage WHERE symbol = ?", ("AAA",))
            row = cursor.fetchone()
        assert row[0] == "AAA"
        assert row[1] == "test"
        assert row[2] == 2
        del db
        gc.collect()
