import threading

import pytest

from src.platform.job_queue import JobQueue, JobStore


def test_job_queue_runs(tmp_path):
    store = JobStore(path=str(tmp_path / "jobs.json"))
    queue = JobQueue(store=store, max_workers=1)

    def work(payload):
        return {"value": payload["x"] + 1}

    try:
        job_id = queue.submit("unit", work, {"x": 2})
        record = queue.wait(job_id, timeout=5)
        assert record is not None
        assert record.status == "success"
        assert record.result["value"] == 3
    finally:
        queue.shutdown()


def test_job_queue_cancel_pending_job(tmp_path):
    store = JobStore(path=str(tmp_path / "jobs.json"))
    queue = JobQueue(store=store, max_workers=1)
    started = threading.Event()
    release = threading.Event()

    def slow_work(_payload):
        started.set()
        release.wait(timeout=5)
        return {"done": True}

    try:
        running_job = queue.submit("slow", slow_work, {})
        assert started.wait(timeout=2)

        queued_job = queue.submit("unit", lambda payload: {"value": payload["x"] + 1}, {"x": 1})
        cancelled = queue.cancel(queued_job)

        assert cancelled.status == "cancelled"
        assert cancelled.cancel_requested is True

        release.set()
        queue.wait(running_job, timeout=5)
    finally:
        queue.shutdown()


def test_job_queue_cancel_running_job_rejected(tmp_path):
    store = JobStore(path=str(tmp_path / "jobs.json"))
    queue = JobQueue(store=store, max_workers=1)
    started = threading.Event()
    release = threading.Event()

    def slow_work(_payload):
        started.set()
        release.wait(timeout=5)
        return {"done": True}

    try:
        running_job = queue.submit("slow", slow_work, {})
        assert started.wait(timeout=2)

        with pytest.raises(RuntimeError):
            queue.cancel(running_job)

        release.set()
        queue.wait(running_job, timeout=5)
    finally:
        queue.shutdown()


def test_job_queue_metrics(tmp_path):
    store = JobStore(path=str(tmp_path / "jobs.json"))
    queue = JobQueue(store=store, max_workers=1)

    try:
        job_id = queue.submit("unit", lambda payload: {"ok": payload["ok"]}, {"ok": True})
        queue.wait(job_id, timeout=5)

        metrics = queue.metrics()
        assert metrics["total_jobs"] >= 1
        assert metrics["success_jobs"] >= 1
        assert metrics["max_workers"] == 1
        assert "queue_delay_ms_p50" in metrics
        assert "run_duration_ms_p50" in metrics
    finally:
        queue.shutdown()


def test_job_store_sqlite_backend(tmp_path):
    store = JobStore(path=str(tmp_path / "jobs.db"))
    queue = JobQueue(store=store, max_workers=1)

    try:
        job_id = queue.submit("unit", lambda payload: {"ok": payload["ok"]}, {"ok": True})
        queue.wait(job_id, timeout=5)
        rec = store.get(job_id)
        assert rec is not None
        assert rec.status == "success"
        assert store.backend_type == "sqlite"
    finally:
        queue.shutdown()


def test_job_queue_submit_idempotency(tmp_path):
    store = JobStore(path=str(tmp_path / "jobs.db"))
    queue = JobQueue(store=store, max_workers=1)

    try:
        job_id_1 = queue.submit(
            "unit",
            lambda payload: {"v": payload["v"]},
            {"v": 1},
            idempotency_key="fixed-001",
        )
        job_id_2 = queue.submit(
            "unit",
            lambda payload: {"v": payload["v"]},
            {"v": 1},
            idempotency_key="fixed-001",
        )
        assert job_id_1 == job_id_2
        queue.wait(job_id_1, timeout=5)
    finally:
        queue.shutdown()


# ---------------------------------------------------------------------------
# Redis backend tests (V4.0-C)
# ---------------------------------------------------------------------------


def test_redis_backend_fallback_to_json(tmp_path):
    """When redis is unavailable, JobStore falls back to in-memory JSON."""
    store = JobStore(path="redis://localhost:19999/0")
    assert store.backend_type == "redis_fallback_json"

    queue = JobQueue(store=store, max_workers=1)
    try:
        job_id = queue.submit("unit", lambda p: {"v": p["v"]}, {"v": 42})
        queue.wait(job_id, timeout=5)
        rec = store.get(job_id)
        assert rec is not None
        assert rec.status == "success"
    finally:
        queue.shutdown()


def test_redis_backend_idempotency_via_fallback():
    """Idempotency works through the fallback backend."""
    store = JobStore(path="redis://localhost:19999/0")
    queue = JobQueue(store=store, max_workers=1)
    try:
        id1 = queue.submit("unit", lambda p: {"ok": True}, {}, idempotency_key="dup")
        id2 = queue.submit("unit", lambda p: {"ok": True}, {}, idempotency_key="dup")
        assert id1 == id2
        queue.wait(id1, timeout=5)
    finally:
        queue.shutdown()


def test_redis_backend_list_via_fallback():
    """List works through the fallback backend."""
    store = JobStore(path="redis://localhost:19999/0")
    queue = JobQueue(store=store, max_workers=1)
    try:
        queue.submit("unit", lambda p: {"ok": True}, {})
        queue.submit("unit", lambda p: {"ok": True}, {})
        jobs = store.list()
        assert len(jobs) >= 2
    finally:
        queue.shutdown()
