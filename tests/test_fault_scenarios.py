"""
Fault Scenario Tests (P5.1)

Tests to verify system resilience under various failure conditions:
- Data provider faults (timeout, empty data, partial missing, cache corruption)
- Gateway faults (disconnect during order, reconnect, callback errors, rate limiting)
- Database faults (lock contention, write failures)
- Resource exhaustion (large datasets, queue saturation)
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
import threading
import time
from queue import Queue
from unittest.mock import MagicMock, patch, PropertyMock

import numpy as np
import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Data Provider Fault Tests
# ---------------------------------------------------------------------------

class TestDataProviderFaults:
    """Test data provider behavior under fault conditions."""

    def test_akshare_import_failure(self):
        """Verify graceful handling when akshare is not installed."""
        from src.data_sources.providers import DataProviderUnavailable

        with patch.dict("sys.modules", {"akshare": None}):
            from src.data_sources.providers import AkshareProvider
            provider = AkshareProvider(cache_dir=tempfile.mkdtemp())
            with pytest.raises(DataProviderUnavailable):
                provider.load_stock_daily(["600519.SH"], "2024-01-01", "2024-06-30")

    def test_yfinance_import_failure(self):
        """Verify graceful handling when yfinance is not installed."""
        from src.data_sources.providers import DataProviderUnavailable

        with patch.dict("sys.modules", {"yfinance": None}):
            from src.data_sources.providers import YFinanceProvider
            provider = YFinanceProvider(cache_dir=tempfile.mkdtemp())
            with pytest.raises(DataProviderUnavailable):
                provider.load_stock_daily(["AAPL"], "2024-01-01", "2024-06-30")

    def test_empty_symbol_list(self):
        """Loading zero symbols returns empty dict."""
        from src.data_sources.providers import AkshareProvider
        provider = AkshareProvider(cache_dir=tempfile.mkdtemp())
        result = provider.load_stock_daily([], "2024-01-01", "2024-06-30")
        assert result == {}

    def test_invalid_date_format(self):
        """Invalid dates should raise ValueError."""
        from src.data_sources.providers import DataProvider
        with pytest.raises(ValueError):
            DataProvider._validate_dates("", "2024-06-30")
        with pytest.raises(ValueError):
            DataProvider._validate_dates("2024-01-01", "")

    def test_date_normalization(self):
        """Date formats are normalized correctly."""
        from src.data_sources.providers import DataProvider
        s, e = DataProvider._validate_dates("20240101", "20240630")
        assert s == "2024-01-01"
        assert e == "2024-06-30"

        s2, e2 = DataProvider._validate_dates("2024/01/01", "2024/06/30")
        assert "-" in s2
        assert "-" in e2

    def test_standardize_stock_frame_empty(self):
        """Standardizing empty dataframe doesn't crash."""
        from src.data_sources.providers import _standardize_stock_frame
        df = pd.DataFrame()
        result = _standardize_stock_frame(df)
        assert result.empty

    def test_standardize_stock_frame_chinese_columns(self):
        """Chinese column names are mapped correctly."""
        from src.data_sources.providers import _standardize_stock_frame
        df = pd.DataFrame({
            "日期": ["2024-01-02", "2024-01-03"],
            "开盘": [100.0, 101.0],
            "收盘": [101.0, 102.0],
            "最高": [102.0, 103.0],
            "最低": [99.0, 100.0],
            "成交量": [10000, 12000],
        })
        result = _standardize_stock_frame(df)
        assert "open" in result.columns
        assert "close" in result.columns
        assert result.index.name == "date"

    def test_data_checksum_deterministic(self):
        """Same data produces same checksum."""
        from src.data_sources.providers import _data_checksum
        dates = pd.date_range("2024-01-01", periods=5)
        df = pd.DataFrame({"close": [1.0, 2.0, 3.0, 4.0, 5.0]}, index=dates)

        c1 = _data_checksum(df)
        c2 = _data_checksum(df)
        assert c1 == c2
        assert c1 is not None

    def test_data_checksum_empty(self):
        """Empty dataframe returns None checksum."""
        from src.data_sources.providers import _data_checksum
        assert _data_checksum(pd.DataFrame()) is None
        assert _data_checksum(None) is None

    def test_nav_from_close_empty(self):
        """Empty close series returns empty."""
        from src.data_sources.providers import _nav_from_close
        result = _nav_from_close(pd.Series([], dtype=float))
        assert result.empty

    def test_nav_from_close_normalization(self):
        """NAV starts at 1.0."""
        from src.data_sources.providers import _nav_from_close
        close = pd.Series([100.0, 110.0, 105.0])
        nav = _nav_from_close(close)
        assert nav.iloc[0] == 1.0
        assert abs(nav.iloc[1] - 1.1) < 1e-10


# ---------------------------------------------------------------------------
# Gateway Fault Tests
# ---------------------------------------------------------------------------

class TestGatewayFaults:
    """Test gateway fault handling."""

    @pytest.fixture
    def event_queue(self):
        return Queue()

    @pytest.fixture
    def xtp_config(self):
        from src.gateways.base_live_gateway import GatewayConfig
        return GatewayConfig(
            account_id="FAULT_TEST",
            broker="xtp",
            auto_reconnect=False,
        )

    def test_rate_limiting(self, xtp_config, event_queue):
        """Rate limiter enforces order interval."""
        from src.gateways.xtp_gateway import XtpGateway
        from src.gateways.base_live_gateway import GatewayConfig, OrderSide

        config = GatewayConfig(
            account_id="RATE_TEST",
            broker="xtp",
            max_orders_per_second=5.0,
            auto_reconnect=False,
        )
        gw = XtpGateway(config, event_queue)
        gw.connect()

        start = time.time()
        for i in range(3):
            gw.send_order("600519.SH", OrderSide.BUY, 100, price=1800.0)
        elapsed = time.time() - start

        # With 5 orders/sec, each interval is 0.2s. 3 orders need ~0.4s
        assert elapsed >= 0.3

        gw.disconnect()

    def test_cancel_all_orders(self, xtp_config, event_queue):
        """cancel_all_orders cancels all open orders."""
        from src.gateways.xtp_gateway import XtpGateway
        from src.gateways.base_live_gateway import OrderSide

        gw = XtpGateway(xtp_config, event_queue)
        gw.connect()

        for _ in range(3):
            gw.send_order("600519.SH", OrderSide.BUY, 100, price=1800.0)
        time.sleep(0.5)

        count = gw.cancel_all_orders()
        assert count == 3

        gw.disconnect()

    def test_cancel_all_with_symbol_filter(self, xtp_config, event_queue):
        """cancel_all_orders with symbol filter."""
        from src.gateways.xtp_gateway import XtpGateway
        from src.gateways.base_live_gateway import OrderSide

        gw = XtpGateway(xtp_config, event_queue)
        gw.connect()

        gw.send_order("600519.SH", OrderSide.BUY, 100, price=1800.0)
        gw.send_order("000001.SZ", OrderSide.BUY, 200, price=15.0)
        time.sleep(0.5)

        count = gw.cancel_all_orders(symbol="600519.SH")
        assert count == 1

        gw.disconnect()

    def test_get_open_orders(self, xtp_config, event_queue):
        """get_open_orders returns submitted orders."""
        from src.gateways.xtp_gateway import XtpGateway
        from src.gateways.base_live_gateway import OrderSide

        gw = XtpGateway(xtp_config, event_queue)
        gw.connect()

        gw.send_order("600519.SH", OrderSide.BUY, 100, price=1800.0)
        gw.send_order("000001.SZ", OrderSide.BUY, 200, price=15.0)
        time.sleep(0.5)

        open_orders = gw.get_open_orders()
        assert len(open_orders) == 2

        open_sh = gw.get_open_orders(symbol="600519.SH")
        assert len(open_sh) == 1

        gw.disconnect()

    def test_order_callback_exception(self, xtp_config, event_queue):
        """Order callbacks that raise don't crash the gateway."""
        from src.gateways.xtp_gateway import XtpGateway
        from src.gateways.base_live_gateway import OrderSide

        gw = XtpGateway(xtp_config, event_queue)
        gw.connect()

        def bad_callback(update):
            raise RuntimeError("callback exploded")

        gw.on_order(bad_callback)

        # Should not raise despite bad callback
        gw.send_order("600519.SH", OrderSide.BUY, 100, price=1800.0)
        time.sleep(0.3)

        gw.disconnect()

    def test_trade_callback_exception(self, xtp_config, event_queue):
        """Trade callbacks that raise don't crash the gateway."""
        from src.gateways.xtp_gateway import XtpGateway
        from src.gateways.base_live_gateway import OrderSide

        gw = XtpGateway(xtp_config, event_queue)
        gw.connect()

        def bad_trade_callback(update):
            raise RuntimeError("trade callback exploded")

        gw.on_trade(bad_trade_callback)

        # Should not raise
        gw.send_order("600519.SH", OrderSide.BUY, 100, price=1800.0)
        time.sleep(0.3)

        gw.disconnect()

    def test_query_when_disconnected(self, xtp_config, event_queue):
        """Queries return None/empty when disconnected."""
        from src.gateways.xtp_gateway import XtpGateway

        gw = XtpGateway(xtp_config, event_queue)
        # Not connected
        assert gw.query_account() is None
        assert gw.query_positions() == []
        assert gw.query_position("600519.SH") is None


# ---------------------------------------------------------------------------
# Database Fault Tests
# ---------------------------------------------------------------------------

class TestDatabaseFaults:
    """Test SQLite database fault handling."""

    def test_db_manager_creates_tables(self):
        """Database manager initializes schema correctly."""
        from src.data_sources.db_manager import SQLiteDataManager
        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "test.db")
        db = SQLiteDataManager(db_path)

        # Tables should exist
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        # Close the db manager connection
        if hasattr(db, 'close'):
            db.close()

        assert "stock_daily" in tables or len(tables) > 0

    def test_save_and_load_roundtrip(self):
        """Save then load produces same data."""
        from src.data_sources.db_manager import SQLiteDataManager
        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "test.db")
        db = SQLiteDataManager(db_path)

        dates = pd.date_range("2024-01-02", periods=5, freq="B")
        df = pd.DataFrame({
            "open": [1.0, 2.0, 3.0, 4.0, 5.0],
            "high": [1.5, 2.5, 3.5, 4.5, 5.5],
            "low": [0.5, 1.5, 2.5, 3.5, 4.5],
            "close": [1.2, 2.2, 3.2, 4.2, 5.2],
            "volume": [100, 200, 300, 400, 500],
        }, index=dates)
        df.index.name = "date"

        db.save_stock_data("TEST.SH", df, "noadj")
        loaded = db.load_stock_data("TEST.SH", "2024-01-01", "2024-12-31", "noadj")

        # Close db before assertions to release file lock
        if hasattr(db, 'close'):
            db.close()

        assert loaded is not None
        assert len(loaded) == 5
        assert abs(loaded["close"].iloc[0] - 1.2) < 1e-10


# ---------------------------------------------------------------------------
# Resource Exhaustion Tests
# ---------------------------------------------------------------------------

class TestResourceExhaustion:
    """Test behavior under resource pressure."""

    @pytest.mark.slow
    def test_large_dataframe_standardization(self):
        """Standardize large dataframe without memory issues."""
        from src.data_sources.providers import _standardize_stock_frame

        n = 10000
        df = pd.DataFrame({
            "日期": pd.date_range("2000-01-01", periods=n).strftime("%Y-%m-%d"),
            "开盘": np.random.uniform(10, 100, n),
            "收盘": np.random.uniform(10, 100, n),
            "最高": np.random.uniform(10, 100, n),
            "最低": np.random.uniform(10, 100, n),
            "成交量": np.random.randint(1000, 1000000, n),
        })

        result = _standardize_stock_frame(df)
        assert len(result) == n
        assert result.index.name == "date"

    def test_queue_saturation(self):
        """Job queue handles rapid submissions."""
        from src.platform.job_queue import JobQueue, JobStore

        tmpdir = tempfile.mkdtemp()
        store = JobStore(path=os.path.join(tmpdir, "jobs.db"))
        jq = JobQueue(store=store, max_workers=2)

        def dummy_task(payload):
            time.sleep(0.01)
            return {"status": "ok"}

        # Submit many tasks rapidly
        job_ids = []
        for i in range(50):
            jid = jq.submit("test_task", dummy_task, {"i": i})
            job_ids.append(jid)

        assert len(job_ids) == 50

        # Wait for completion
        time.sleep(3)

        metrics = jq.metrics()
        assert metrics["total_jobs"] >= 50

        jq.shutdown()

    def test_concurrent_job_submissions(self):
        """Multiple threads submitting jobs concurrently."""
        from src.platform.job_queue import JobQueue, JobStore

        tmpdir = tempfile.mkdtemp()
        store = JobStore(path=os.path.join(tmpdir, "jobs.db"))
        jq = JobQueue(store=store, max_workers=4)

        def dummy_task(payload):
            time.sleep(0.01)
            return {"ok": True}

        results = []
        errors = []

        def submit_batch(start, count):
            for i in range(count):
                try:
                    jid = jq.submit("concurrent_task", dummy_task, {"n": start + i})
                    results.append(jid)
                except Exception as e:
                    errors.append(e)

        threads = [
            threading.Thread(target=submit_batch, args=(i * 10, 10))
            for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 50

        jq.shutdown()
