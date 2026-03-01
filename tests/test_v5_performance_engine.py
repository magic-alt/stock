"""
Tests for V5.0-B: DuckDB storage, vectorized computation,
multi-frequency bar chain, and stream dispatcher.
"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

try:
    import duckdb  # noqa: F401
    _HAS_DUCKDB = True
except ImportError:
    _HAS_DUCKDB = False


# ===========================================================================
# B-2: DuckDB Time Series Store
# ===========================================================================

@pytest.mark.skipif(not _HAS_DUCKDB, reason="duckdb not installed")
class TestDuckDBTimeSeriesStore:
    """Tests for src/data_sources/duckdb_store.py."""

    def _make_ohlcv(self, days: int = 50, start: str = "2024-01-01") -> pd.DataFrame:
        rng = pd.date_range(start, periods=days, freq="B")
        rng_np = np.random.default_rng(42)
        close = 100 + np.cumsum(rng_np.normal(0, 1, days))
        return pd.DataFrame({
            "open": close - rng_np.uniform(0.5, 1.5, days),
            "high": close + rng_np.uniform(0.5, 2.0, days),
            "low": close - rng_np.uniform(0.5, 2.0, days),
            "close": close,
            "volume": rng_np.integers(10000, 100000, days).astype(float),
        }, index=rng)

    def test_ingest_and_query(self):
        from src.data_sources.duckdb_store import DuckDBTimeSeriesStore, DuckDBConfig
        store = DuckDBTimeSeriesStore(DuckDBConfig(db_path=":memory:"))
        df = self._make_ohlcv(30)
        rows = store.ingest("600519.SH", df, freq="daily")
        assert rows == 30
        result = store.query("600519.SH", freq="daily")
        assert len(result) == 30
        assert "close" in result.columns
        store.close()

    def test_query_date_range(self):
        from src.data_sources.duckdb_store import DuckDBTimeSeriesStore, DuckDBConfig
        store = DuckDBTimeSeriesStore(DuckDBConfig(db_path=":memory:"))
        df = self._make_ohlcv(50)
        store.ingest("600519.SH", df)
        result = store.query("600519.SH", start="2024-01-15", end="2024-02-15")
        assert len(result) > 0
        assert len(result) < 50
        store.close()

    def test_query_multiple(self):
        from src.data_sources.duckdb_store import DuckDBTimeSeriesStore, DuckDBConfig
        store = DuckDBTimeSeriesStore(DuckDBConfig(db_path=":memory:"))
        for sym in ["A.SH", "B.SH", "C.SH"]:
            store.ingest(sym, self._make_ohlcv(20))
        result = store.query_multiple(["A.SH", "C.SH"])
        assert len(result) == 2
        assert len(result["A.SH"]) == 20
        store.close()

    def test_list_symbols(self):
        from src.data_sources.duckdb_store import DuckDBTimeSeriesStore, DuckDBConfig
        store = DuckDBTimeSeriesStore(DuckDBConfig(db_path=":memory:"))
        for sym in ["A.SH", "B.SH"]:
            store.ingest(sym, self._make_ohlcv(10))
        symbols = store.list_symbols()
        assert set(symbols) == {"A.SH", "B.SH"}
        store.close()

    def test_count(self):
        from src.data_sources.duckdb_store import DuckDBTimeSeriesStore, DuckDBConfig
        store = DuckDBTimeSeriesStore(DuckDBConfig(db_path=":memory:"))
        store.ingest("A.SH", self._make_ohlcv(10))
        store.ingest("B.SH", self._make_ohlcv(20))
        assert store.count() == 30
        assert store.count(symbol="A.SH") == 10
        store.close()

    def test_delete(self):
        from src.data_sources.duckdb_store import DuckDBTimeSeriesStore, DuckDBConfig
        store = DuckDBTimeSeriesStore(DuckDBConfig(db_path=":memory:"))
        store.ingest("A.SH", self._make_ohlcv(10))
        assert store.count() == 10
        store.delete("A.SH")
        assert store.count() == 0
        store.close()

    def test_replace_on_ingest(self):
        from src.data_sources.duckdb_store import DuckDBTimeSeriesStore, DuckDBConfig
        store = DuckDBTimeSeriesStore(DuckDBConfig(db_path=":memory:"))
        store.ingest("A.SH", self._make_ohlcv(10))
        store.ingest("A.SH", self._make_ohlcv(20), replace=True)
        assert store.count() == 20
        store.close()

    def test_multi_freq_ingest(self):
        from src.data_sources.duckdb_store import DuckDBTimeSeriesStore, DuckDBConfig
        store = DuckDBTimeSeriesStore(DuckDBConfig(db_path=":memory:"))
        store.ingest("A.SH", self._make_ohlcv(10), freq="daily")
        store.ingest("A.SH", self._make_ohlcv(50), freq="1min")
        assert store.count(freq="daily") == 10
        assert store.count(freq="1min") == 50
        store.close()

    def test_stats(self):
        from src.data_sources.duckdb_store import DuckDBTimeSeriesStore, DuckDBConfig
        store = DuckDBTimeSeriesStore(DuckDBConfig(db_path=":memory:"))
        store.ingest("A.SH", self._make_ohlcv(10))
        s = store.stats()
        assert s["total_rows"] == 10
        assert s["symbols"] == 1
        assert "daily" in s["frequencies"]
        store.close()

    def test_file_persistence(self):
        from src.data_sources.duckdb_store import DuckDBTimeSeriesStore, DuckDBConfig
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.duckdb")
            store1 = DuckDBTimeSeriesStore(DuckDBConfig(db_path=path))
            store1.ingest("A.SH", self._make_ohlcv(15))
            store1.close()
            # Reopen
            store2 = DuckDBTimeSeriesStore(DuckDBConfig(db_path=path))
            assert store2.count() == 15
            store2.close()

    def test_aggregate_daily(self):
        from src.data_sources.duckdb_store import DuckDBTimeSeriesStore, DuckDBConfig
        store = DuckDBTimeSeriesStore(DuckDBConfig(db_path=":memory:"))
        # Create minute-like data (use hourly index as proxy)
        idx = pd.date_range("2024-01-02 09:30", periods=240, freq="min")
        rng_np = np.random.default_rng(42)
        close = 100 + np.cumsum(rng_np.normal(0, 0.1, 240))
        df = pd.DataFrame({
            "open": close - 0.1,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": rng_np.integers(100, 1000, 240).astype(float),
        }, index=idx)
        store.ingest("A.SH", df, freq="1min")
        agg = store.aggregate("A.SH", from_freq="1min", to_freq="daily")
        assert len(agg) >= 1
        assert "close" in agg.columns
        store.close()

    def test_export_parquet(self):
        from src.data_sources.duckdb_store import DuckDBTimeSeriesStore, DuckDBConfig
        store = DuckDBTimeSeriesStore(DuckDBConfig(db_path=":memory:"))
        store.ingest("A.SH", self._make_ohlcv(10))
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "export.parquet")
            store.export_parquet(path, symbol="A.SH")
            assert os.path.exists(path)
            # Verify parquet content
            df = pd.read_parquet(path)
            assert len(df) == 10
        store.close()

    def test_empty_ingest(self):
        from src.data_sources.duckdb_store import DuckDBTimeSeriesStore, DuckDBConfig
        store = DuckDBTimeSeriesStore(DuckDBConfig(db_path=":memory:"))
        rows = store.ingest("A.SH", pd.DataFrame())
        assert rows == 0
        store.close()


# ===========================================================================
# B-3: Vectorized computation layer
# ===========================================================================

class TestVectorizedComputation:
    """Tests for src/core/vectorized.py."""

    def _make_nav(self, n: int = 252) -> np.ndarray:
        rng = np.random.default_rng(42)
        returns = rng.normal(0.0005, 0.015, n)
        nav = 1.0 * np.cumprod(1 + returns)
        return nav

    def test_sharpe_ratio_fast(self):
        from src.core.vectorized import _sharpe_ratio_fast
        returns = np.array([0.01, -0.005, 0.008, -0.003, 0.012, 0.002, -0.001])
        result = _sharpe_ratio_fast(returns)
        assert isinstance(result, float)
        assert result > 0

    def test_max_drawdown_fast(self):
        from src.core.vectorized import _max_drawdown_fast
        nav = np.array([1.0, 1.1, 1.2, 0.9, 1.0, 1.3])
        mdd = _max_drawdown_fast(nav)
        assert mdd == pytest.approx(0.25, abs=0.01)  # 1.2 → 0.9 = 25%

    def test_sortino_ratio_fast(self):
        from src.core.vectorized import _sortino_ratio_fast
        returns = np.array([0.01, -0.005, 0.008, -0.003, 0.012])
        result = _sortino_ratio_fast(returns)
        assert isinstance(result, float)

    def test_calmar_ratio_fast(self):
        from src.core.vectorized import _calmar_ratio_fast
        nav = np.array([1.0, 1.05, 1.1, 1.0, 1.15, 1.2])
        result = _calmar_ratio_fast(nav)
        assert isinstance(result, float)
        assert result > 0

    def test_compute_metrics_fast(self):
        from src.core.vectorized import compute_metrics_fast
        nav = self._make_nav(252)
        m = compute_metrics_fast(nav)
        assert "cum_return" in m
        assert "sharpe" in m
        assert "sortino" in m
        assert "mdd" in m
        assert "calmar" in m
        assert "skewness" in m
        assert "kurtosis" in m
        assert m["mdd"] >= 0

    def test_compute_metrics_short_nav(self):
        from src.core.vectorized import compute_metrics_fast
        m = compute_metrics_fast(np.array([1.0]))
        assert np.isnan(m["sharpe"])

    def test_var_es_fast(self):
        from src.core.vectorized import compute_var_es_fast
        rng = np.random.default_rng(42)
        returns = rng.normal(0.001, 0.02, 500)
        var95, es95 = compute_var_es_fast(returns, 0.95)
        assert var95 < 0  # VaR is a loss
        assert es95 < var95  # ES is more extreme than VaR

    def test_var_es_short(self):
        from src.core.vectorized import compute_var_es_fast
        var, es = compute_var_es_fast(np.array([0.01, 0.02]))
        assert np.isnan(var)

    def test_rolling_volatility(self):
        from src.core.vectorized import rolling_volatility
        nav = pd.Series(self._make_nav(100), index=pd.date_range("2024-01-01", periods=100))
        vol = rolling_volatility(nav, window=20)
        assert len(vol) == 99  # one less due to pct_change
        assert not vol.iloc[-1] != vol.iloc[-1]  # not NaN at end

    def test_drawdown_series(self):
        from src.core.vectorized import drawdown_series
        nav = pd.Series([1.0, 1.1, 1.2, 0.9, 1.0])
        dd = drawdown_series(nav)
        assert dd.iloc[0] == 0.0
        assert dd.iloc[3] == pytest.approx(-0.25, abs=0.01)

    def test_rolling_volatility_with_series(self):
        from src.core.vectorized import _rolling_volatility
        returns = np.array([0.01, -0.02, 0.015, -0.005, 0.01] * 10)
        vol = _rolling_volatility(returns, window=5)
        assert len(vol) == 50
        assert np.isnan(vol[0])  # before window
        assert not np.isnan(vol[-1])  # after window


# ===========================================================================
# B-4: Multi-frequency bar chain & stream dispatcher
# ===========================================================================

class TestMultiFreqBarChain:
    """Tests for MultiFreqBarChain in realtime_data.py."""

    def _make_tick(self, symbol: str, price: float, ts: datetime) -> object:
        from src.core.interfaces import TickData
        return TickData(symbol=symbol, timestamp=ts, last_price=price, volume=100.0)

    def test_chain_creates_builders(self):
        from src.core.realtime_data import MultiFreqBarChain
        chain = MultiFreqBarChain("A.SH", [1, 5])
        assert 1 in chain._builders
        assert 5 in chain._builders

    def test_chain_callbacks_fire(self):
        from src.core.realtime_data import MultiFreqBarChain
        chain = MultiFreqBarChain("A.SH", [1, 5])
        bars_1m = []
        chain.on_bar(1, lambda bar: bars_1m.append(bar))

        base = datetime(2024, 1, 2, 9, 30, 0)
        # First minute tick
        tick1 = self._make_tick("A.SH", 100.0, base + timedelta(seconds=10))
        chain.update(tick1)
        # Second minute tick triggers first bar
        tick2 = self._make_tick("A.SH", 101.0, base + timedelta(minutes=1, seconds=10))
        chain.update(tick2)
        assert len(bars_1m) == 1

    def test_chain_current_bars(self):
        from src.core.realtime_data import MultiFreqBarChain
        chain = MultiFreqBarChain("A.SH", [1])
        tick = self._make_tick("A.SH", 100.0, datetime(2024, 1, 2, 9, 30, 10))
        chain.update(tick)
        current = chain.current_bars
        assert 1 in current
        assert current[1] is not None

    def test_chain_history(self):
        from src.core.realtime_data import MultiFreqBarChain
        chain = MultiFreqBarChain("A.SH", [1])
        base = datetime(2024, 1, 2, 9, 30, 0)
        for i in range(5):
            tick = self._make_tick("A.SH", 100.0 + i, base + timedelta(minutes=i, seconds=10))
            chain.update(tick)
        hist = chain.get_history(1, limit=10)
        assert len(hist) >= 3  # at least 3 completed bars


class TestStreamDispatcher:
    """Tests for StreamDispatcher in realtime_data.py."""

    def test_subscribe_and_publish(self):
        from src.core.realtime_data import StreamDispatcher
        disp = StreamDispatcher()
        received = []
        disp.subscribe("test.topic", lambda d: received.append(d))
        count = disp.publish("test.topic", {"value": 42})
        assert count == 1
        assert received == [{"value": 42}]

    def test_wildcard_subscribe(self):
        from src.core.realtime_data import StreamDispatcher
        disp = StreamDispatcher()
        received = []
        disp.subscribe("tick.*", lambda d: received.append(d))
        disp.publish("tick.600519.SH", {"price": 1800})
        disp.publish("tick.000001.SZ", {"price": 12})
        assert len(received) == 2

    def test_unsubscribe(self):
        from src.core.realtime_data import StreamDispatcher
        disp = StreamDispatcher()
        received = []
        cb = lambda d: received.append(d)
        disp.subscribe("test", cb)
        disp.publish("test", "a")
        disp.unsubscribe("test", cb)
        disp.publish("test", "b")
        assert received == ["a"]

    def test_publish_tick(self):
        from src.core.realtime_data import StreamDispatcher
        from src.core.interfaces import TickData
        disp = StreamDispatcher()
        received = []
        disp.subscribe("tick.A.SH", lambda d: received.append(d))
        tick = TickData(symbol="A.SH", timestamp=datetime.now(), last_price=100.0)
        disp.publish_tick(tick)
        assert len(received) == 1

    def test_publish_bar(self):
        from src.core.realtime_data import StreamDispatcher
        from src.core.interfaces import BarData
        disp = StreamDispatcher()
        received = []
        disp.subscribe("bar.1.A.SH", lambda d: received.append(d))
        bar = BarData(symbol="A.SH", timestamp=datetime.now(), open=100, high=101, low=99, close=100.5)
        disp.publish_bar(bar, interval=1)
        assert len(received) == 1

    def test_stats(self):
        from src.core.realtime_data import StreamDispatcher
        disp = StreamDispatcher()
        disp.subscribe("t", lambda d: None)
        disp.publish("t", "x")
        disp.publish("t", "y")
        assert disp.stats["t"] == 2

    def test_subscriber_count(self):
        from src.core.realtime_data import StreamDispatcher
        disp = StreamDispatcher()
        disp.subscribe("a", lambda d: None)
        disp.subscribe("b", lambda d: None)
        assert disp.subscriber_count == 2

    def test_error_in_callback_doesnt_break_dispatch(self):
        from src.core.realtime_data import StreamDispatcher
        disp = StreamDispatcher()
        def bad_cb(d):
            raise ValueError("boom")
        good_results = []
        disp.subscribe("t", bad_cb)
        disp.subscribe("t", lambda d: good_results.append(d))
        count = disp.publish("t", "x")
        assert count == 1  # good callback succeeded
        assert good_results == ["x"]

    def test_no_subscribers(self):
        from src.core.realtime_data import StreamDispatcher
        disp = StreamDispatcher()
        count = disp.publish("nonexistent", "data")
        assert count == 0
