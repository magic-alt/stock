from src.platform.job_queue import JobQueue, JobStore


def test_job_queue_runs(tmp_path):
    store = JobStore(path=str(tmp_path / "jobs.json"))
    queue = JobQueue(store=store, max_workers=1)

    def work(payload):
        return {"value": payload["x"] + 1}

    job_id = queue.submit("unit", work, {"x": 2})
    record = queue.wait(job_id, timeout=5)
    assert record is not None
    assert record.status == "success"
    assert record.result["value"] == 3
