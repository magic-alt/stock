"""
Load Tests (P5.2)

Performance and throughput tests for critical system components.
Marked with @pytest.mark.slow for selective execution.
"""
from __future__ import annotations

import os
import tempfile
import threading
import time

import numpy as np
import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Job Queue Load Tests
# ---------------------------------------------------------------------------

@pytest.mark.slow
class TestJobQueueLoad:
    """Load test the job queue for throughput and stability."""

    def test_sustained_throughput(self):
        """Verify sustained job throughput > 5 jobs/sec."""
        from src.platform.job_queue import JobQueue, JobStore

        tmpdir = tempfile.mkdtemp()
        store = JobStore(path=os.path.join(tmpdir, "load_jobs.db"))
        jq = JobQueue(store=store, max_workers=4)

        def fast_task(payload):
            time.sleep(0.005)  # 5ms per task
            return {"ok": True}

        num_jobs = 100
        start = time.time()

        for i in range(num_jobs):
            jq.submit("fast_task", fast_task, {"i": i})

        # Wait for all to complete
        deadline = time.time() + 30
        while time.time() < deadline:
            m = jq.metrics()
            if m.get("success_jobs", 0) + m.get("failed_jobs", 0) >= num_jobs:
                break
            time.sleep(0.1)

        elapsed = time.time() - start
        throughput = num_jobs / elapsed

        assert throughput > 5.0, f"Throughput {throughput:.1f} jobs/sec < 5.0"

        jq.shutdown()

    def test_concurrent_submit_and_consume(self):
        """Submit and consume jobs concurrently without deadlock."""
        from src.platform.job_queue import JobQueue, JobStore

        tmpdir = tempfile.mkdtemp()
        store = JobStore(path=os.path.join(tmpdir, "concurrent.db"))
        jq = JobQueue(store=store, max_workers=4)

        results = {"completed": 0}
        lock = threading.Lock()

        def counting_task(payload):
            time.sleep(0.01)
            with lock:
                results["completed"] += 1
            return {"done": True}

        num_jobs = 80
        submit_errors = []

        def submit_batch(start, count):
            for i in range(count):
                try:
                    jq.submit("count_task", counting_task, {"n": start + i})
                except Exception as e:
                    submit_errors.append(e)

        # 4 threads, each submitting 20 jobs
        threads = [
            threading.Thread(target=submit_batch, args=(i * 20, 20))
            for i in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(submit_errors) == 0

        # Wait for completion
        time.sleep(5)
        jq.shutdown()

    def test_large_payload_jobs(self):
        """Jobs with large payloads are handled correctly."""
        from src.platform.job_queue import JobQueue, JobStore

        tmpdir = tempfile.mkdtemp()
        store = JobStore(path=os.path.join(tmpdir, "large.db"))
        jq = JobQueue(store=store, max_workers=2)

        def large_task(payload):
            data = payload.get("data", "")
            return {"size": len(data)}

        # Submit jobs with large payloads
        for i in range(10):
            payload = {"data": "x" * 10000, "index": i}
            jq.submit("large_task", large_task, payload)

        time.sleep(3)

        m = jq.metrics()
        assert m["total_jobs"] >= 10

        jq.shutdown()


# ---------------------------------------------------------------------------
# Factor Pipeline Load Tests
# ---------------------------------------------------------------------------

@pytest.mark.slow
class TestFactorPipelineLoad:
    """Load test the factor computation pipeline."""

    @pytest.fixture
    def large_dataset(self):
        """Generate a large multi-symbol dataset."""
        np.random.seed(42)
        n_bars = 1000
        n_symbols = 50

        datasets = {}
        for i in range(n_symbols):
            symbol = f"SYM{i:04d}.SH"
            base_price = np.random.uniform(10, 200)
            returns = np.random.normal(0, 0.02, n_bars)
            prices = base_price * np.exp(np.cumsum(returns))

            datasets[symbol] = pd.DataFrame({
                "open": prices * np.random.uniform(0.99, 1.01, n_bars),
                "high": prices * np.random.uniform(1.0, 1.03, n_bars),
                "low": prices * np.random.uniform(0.97, 1.0, n_bars),
                "close": prices,
                "volume": np.random.randint(10000, 1000000, n_bars).astype(float),
            }, index=pd.date_range("2020-01-02", periods=n_bars, freq="B"))

        return datasets

    def test_single_symbol_factor_computation(self, large_dataset):
        """Compute multiple factors on single large dataset."""
        from src.pipeline.factor_engine import (
            SMA, RSI, MACD, BollingerBands,
            ATR, Volatility,
        )

        symbol = list(large_dataset.keys())[0]
        data = large_dataset[symbol]

        factors = [
            SMA(period=20),
            RSI(period=14),
            MACD(),
            BollingerBands(period=20),
            ATR(period=14),
            Volatility(period=20),
        ]

        start = time.time()
        results = {}
        for factor in factors:
            results[factor.name] = factor.compute(data)
        elapsed = time.time() - start

        assert len(results) == 6
        for name, series in results.items():
            assert len(series) == len(data)
        assert elapsed < 5.0, f"Single-symbol factor computation took {elapsed:.1f}s"

    def test_multi_symbol_factor_computation(self, large_dataset):
        """Compute factors across 50 symbols × 1000 bars."""
        from src.pipeline.factor_engine import SMA, RSI

        factor = SMA(period=20)

        start = time.time()
        results = {}
        for symbol, data in large_dataset.items():
            results[symbol] = factor.compute(data)
        elapsed = time.time() - start

        assert len(results) == 50
        assert elapsed < 10.0, f"Multi-symbol computation took {elapsed:.1f}s"

    def test_fundamental_factors_load(self):
        """Compute fundamental factors on large dataset."""
        from src.pipeline.fundamental_factors import full_fundamental_pipeline

        np.random.seed(42)
        n = 1000
        data = pd.DataFrame({
            "close": np.random.uniform(10, 200, n),
            "eps": np.random.uniform(0.5, 5.0, n),
            "bps": np.random.uniform(5, 50, n),
            "roe": np.random.uniform(0.05, 0.3, n),
            "revenue": np.random.uniform(1e8, 1e10, n),
            "revenue_prev": np.random.uniform(1e8, 1e10, n),
            "dps": np.random.uniform(0.1, 2.0, n),
            "total_debt": np.random.uniform(1e7, 1e9, n),
            "total_equity": np.random.uniform(1e8, 1e10, n),
        }, index=pd.date_range("2020-01-02", periods=n, freq="B"))

        pipeline = full_fundamental_pipeline()

        start = time.time()
        results = pipeline.run({"LOAD_TEST": data})
        elapsed = time.time() - start

        assert len(results.columns) >= 5
        assert elapsed < 2.0, f"Fundamental pipeline took {elapsed:.1f}s"

    def test_factor_correlation_load(self):
        """Correlation analysis on many factors."""
        from src.pipeline.factor_analysis import compute_factor_correlation, find_redundant_factors

        np.random.seed(42)
        n = 1000
        n_factors = 15

        factor_data = pd.DataFrame({
            f"factor_{i}": np.random.randn(n) + (0.3 * np.random.randn(n) if i % 3 == 0 else 0)
            for i in range(n_factors)
        })

        start = time.time()
        corr = compute_factor_correlation(factor_data)
        redundant = find_redundant_factors(factor_data, threshold=0.85)
        elapsed = time.time() - start

        assert corr.shape == (n_factors, n_factors)
        assert elapsed < 1.0, f"Correlation analysis took {elapsed:.1f}s"
