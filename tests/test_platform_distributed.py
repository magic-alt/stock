"""
Tests for distributed backtest runner backends.
"""
import pytest

from src.platform.distributed import (
    DistributedRunner,
    LocalProcessPoolBackend,
)


def _identity_job(payload):
    return {"value": payload.get("x", 0) + 1}


def _failing_job(payload):
    if payload.get("fail"):
        raise ValueError("intentional failure")
    return {"value": payload.get("x", 0)}


class TestLocalProcessPoolBackend:
    def test_submit_and_collect(self):
        backend = LocalProcessPoolBackend(max_workers=2)
        backend.submit(_identity_job, {"x": 1})
        backend.submit(_identity_job, {"x": 2})
        results = backend.collect_results()
        backend.shutdown()

        values = sorted(r["value"] for r in results)
        assert values == [2, 3]

    def test_multiple_payloads(self):
        backend = LocalProcessPoolBackend(max_workers=2)
        for i in range(5):
            backend.submit(_identity_job, {"x": i})
        results = backend.collect_results()
        backend.shutdown()
        assert len(results) == 5

    def test_failure_isolation(self):
        backend = LocalProcessPoolBackend(max_workers=2)
        backend.submit(_identity_job, {"x": 1})
        backend.submit(_failing_job, {"fail": True})
        results = backend.collect_results()
        backend.shutdown()

        statuses = [r.get("status", "ok") for r in results]
        assert "failed" in statuses
        assert len(results) == 2

    def test_max_workers_respected(self):
        backend = LocalProcessPoolBackend(max_workers=1)
        assert backend.max_workers == 1
        backend.shutdown()


class TestDistributedRunner:
    def test_default_backend_is_local(self):
        runner = DistributedRunner(backend="local", max_workers=1)
        assert runner.backend_name == "local"
        runner.shutdown()

    def test_progress_callback(self):
        calls = []

        def cb(done, total):
            calls.append((done, total))

        runner = DistributedRunner(backend="local", max_workers=1, progress_callback=cb)
        results = runner.run(_identity_job, [{"x": 1}, {"x": 2}])
        runner.shutdown()

        assert len(results) == 2
        assert (0, 2) in calls
        assert (2, 2) in calls

    def test_run_distributed_backtests_compat(self):
        from src.platform.distributed import run_distributed_backtests

        results = run_distributed_backtests(
            [{"strategy": "test", "symbols": ["A"], "start_date": "2020-01-01", "end_date": "2020-01-02"}],
            max_workers=1,
            backend="local",
        )
        assert isinstance(results, list)
        assert len(results) == 1


class TestRayBackend:
    @pytest.fixture(autouse=True)
    def skip_if_no_ray(self):
        pytest.importorskip("ray")

    def test_ray_submit_and_collect(self):
        from src.platform.distributed import RayBackend

        backend = RayBackend()
        backend.submit(_identity_job, {"x": 5})
        results = backend.collect_results()
        backend.shutdown()
        assert results[0]["value"] == 6


class TestDaskBackend:
    @pytest.fixture(autouse=True)
    def skip_if_no_dask(self):
        pytest.importorskip("dask.distributed")

    def test_dask_submit_and_collect(self):
        from dask.distributed import Client
        from src.platform.distributed import DaskBackend

        client = Client(processes=False)
        backend = DaskBackend(client=client)
        backend.submit(_identity_job, {"x": 5})
        results = backend.collect_results()
        backend.shutdown()
        client.close()
        assert results[0]["value"] == 6
