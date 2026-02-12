"""
Lightweight job queue for platform orchestration.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from concurrent.futures import CancelledError, Future, ThreadPoolExecutor
from collections import Counter
import json
import os
import threading
import uuid
from typing import Any, Callable, Dict, List, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class JobRecord:
    job_id: str
    task_type: str
    status: str
    payload: Dict[str, Any]
    created_at: str = field(default_factory=_utc_now)
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    cancelled_at: Optional[str] = None
    cancel_requested: bool = False
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class JobStore:
    """JSON-backed job registry."""

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._jobs: Dict[str, JobRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self.path or not os.path.exists(self.path):
            return
        with open(self.path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        for item in data:
            # Backward compatibility for historical records without new fields.
            item.setdefault("cancelled_at", None)
            item.setdefault("cancel_requested", False)
            self._jobs[item["job_id"]] = JobRecord(**item)

    def _save(self) -> None:
        if not self.path:
            return
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump([asdict(j) for j in self._jobs.values()], fh, indent=2, ensure_ascii=False)

    def add(self, record: JobRecord) -> None:
        with self._lock:
            self._jobs[record.job_id] = record
            self._save()

    def update(self, job_id: str, **changes: Any) -> JobRecord:
        with self._lock:
            if job_id not in self._jobs:
                raise KeyError(f"Job not found: {job_id}")
            record = self._jobs[job_id]
            for key, value in changes.items():
                setattr(record, key, value)
            self._jobs[job_id] = record
            self._save()
            return record

    def get(self, job_id: str) -> Optional[JobRecord]:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> List[JobRecord]:
        with self._lock:
            return list(self._jobs.values())


class JobQueue:
    """Thread-based task queue with status tracking."""

    def __init__(self, store: Optional[JobStore] = None, max_workers: int = 4) -> None:
        self.store = store or JobStore()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._max_workers = max_workers
        self._futures: Dict[str, Future] = {}
        self._futures_lock = threading.Lock()

    def submit(
        self,
        task_type: str,
        func: Callable[[Dict[str, Any]], Dict[str, Any]],
        payload: Dict[str, Any],
    ) -> str:
        job_id = str(uuid.uuid4())
        record = JobRecord(job_id=job_id, task_type=task_type, status="pending", payload=payload)
        self.store.add(record)

        def _run() -> Dict[str, Any]:
            self.store.update(job_id, status="running", started_at=_utc_now())
            try:
                result = func(payload)
                self.store.update(job_id, status="success", finished_at=_utc_now(), result=result)
                return result
            except Exception as exc:
                self.store.update(job_id, status="failed", finished_at=_utc_now(), error=str(exc))
                raise

        future = self._executor.submit(_run)

        def _forget_done(_fut: Future) -> None:
            with self._futures_lock:
                self._futures.pop(job_id, None)

        with self._futures_lock:
            self._futures[job_id] = future
        future.add_done_callback(_forget_done)
        return job_id

    def wait(self, job_id: str, timeout: Optional[float] = None) -> Optional[JobRecord]:
        with self._futures_lock:
            future = self._futures.get(job_id)
        if future is not None:
            try:
                future.result(timeout=timeout)
            except CancelledError:
                pass
        return self.store.get(job_id)

    def cancel(self, job_id: str) -> JobRecord:
        """
        Cancel a pending job.

        Python threads cannot be forcefully terminated. If a job is already
        running, cancellation is rejected with RuntimeError.
        """
        record = self.store.get(job_id)
        if record is None:
            raise KeyError(f"Job not found: {job_id}")
        if record.status in {"success", "failed", "cancelled"}:
            return record

        self.store.update(job_id, cancel_requested=True)
        with self._futures_lock:
            future = self._futures.get(job_id)
        if future is None:
            raise RuntimeError("Job has no active future to cancel")

        if future.cancel():
            now = _utc_now()
            return self.store.update(
                job_id,
                status="cancelled",
                cancelled_at=now,
                finished_at=now,
                error="cancelled_by_user",
            )
        raise RuntimeError("Job is already running and cannot be cancelled safely")

    def metrics(self) -> Dict[str, Any]:
        """Return lightweight queue metrics for operational monitoring."""
        jobs = self.store.list()
        status_counter = Counter(j.status for j in jobs)
        with self._futures_lock:
            in_flight = sum(1 for f in self._futures.values() if not f.done())
        return {
            "total_jobs": len(jobs),
            "pending_jobs": status_counter.get("pending", 0),
            "running_jobs": status_counter.get("running", 0),
            "success_jobs": status_counter.get("success", 0),
            "failed_jobs": status_counter.get("failed", 0),
            "cancelled_jobs": status_counter.get("cancelled", 0),
            "max_workers": self._max_workers,
            "in_flight_futures": in_flight,
        }

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False)

