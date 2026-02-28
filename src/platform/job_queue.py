"""
Lightweight job queue for platform orchestration.

Features:
- JSON or SQLite backed job store
- Pending job cancellation
- Optional idempotent submission via idempotency_key
- Operational metrics with queue-delay/run-duration percentiles
"""
from __future__ import annotations

from collections import Counter
from concurrent.futures import CancelledError, Future, ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import os
import sqlite3
import threading
import uuid
from typing import Any, Callable, Dict, List, Optional, Protocol


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_ts(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _safe_quantile(values: List[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    pos = (len(ordered) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    frac = pos - lo
    return float(ordered[lo] + (ordered[hi] - ordered[lo]) * frac)


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
    idempotency_key: Optional[str] = None


class _StoreBackend(Protocol):
    def add(self, record: JobRecord) -> None:
        ...

    def update(self, job_id: str, **changes: Any) -> JobRecord:
        ...

    def get(self, job_id: str) -> Optional[JobRecord]:
        ...

    def list(self) -> List[JobRecord]:
        ...

    def find_by_idempotency(self, task_type: str, idempotency_key: str) -> Optional[JobRecord]:
        ...


class _JsonJobStoreBackend:
    def __init__(self, path: Optional[str]) -> None:
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
            item.setdefault("cancelled_at", None)
            item.setdefault("cancel_requested", False)
            item.setdefault("idempotency_key", None)
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

    def find_by_idempotency(self, task_type: str, idempotency_key: str) -> Optional[JobRecord]:
        with self._lock:
            for record in self._jobs.values():
                if record.task_type == task_type and record.idempotency_key == idempotency_key:
                    return record
        return None


class _SqliteJobStoreBackend:
    def __init__(self, path: str) -> None:
        self.path = path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    task_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    cancelled_at TEXT,
                    cancel_requested INTEGER NOT NULL DEFAULT 0,
                    result TEXT,
                    error TEXT,
                    idempotency_key TEXT
                )
                """
            )
            self._conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_jobs_task_idempotency
                ON jobs (task_type, idempotency_key)
                """
            )

    @staticmethod
    def _encode(value: Any) -> Optional[str]:
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def _decode(text: Optional[str], default: Any) -> Any:
        if text is None:
            return default
        return json.loads(text)

    def _row_to_record(self, row: sqlite3.Row) -> JobRecord:
        return JobRecord(
            job_id=row["job_id"],
            task_type=row["task_type"],
            status=row["status"],
            payload=self._decode(row["payload"], {}),
            created_at=row["created_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            cancelled_at=row["cancelled_at"],
            cancel_requested=bool(row["cancel_requested"]),
            result=self._decode(row["result"], None),
            error=row["error"],
            idempotency_key=row["idempotency_key"],
        )

    def add(self, record: JobRecord) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO jobs (
                    job_id, task_type, status, payload, created_at,
                    started_at, finished_at, cancelled_at, cancel_requested,
                    result, error, idempotency_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.job_id,
                    record.task_type,
                    record.status,
                    self._encode(record.payload),
                    record.created_at,
                    record.started_at,
                    record.finished_at,
                    record.cancelled_at,
                    1 if record.cancel_requested else 0,
                    self._encode(record.result),
                    record.error,
                    record.idempotency_key,
                ),
            )

    def update(self, job_id: str, **changes: Any) -> JobRecord:
        if not changes:
            rec = self.get(job_id)
            if rec is None:
                raise KeyError(f"Job not found: {job_id}")
            return rec

        field_map = {
            "status": "status",
            "started_at": "started_at",
            "finished_at": "finished_at",
            "cancelled_at": "cancelled_at",
            "cancel_requested": "cancel_requested",
            "result": "result",
            "error": "error",
            "idempotency_key": "idempotency_key",
        }
        sets: List[str] = []
        values: List[Any] = []

        for key, value in changes.items():
            if key not in field_map:
                continue
            col = field_map[key]
            if key == "result":
                value = self._encode(value)
            elif key == "cancel_requested":
                value = 1 if bool(value) else 0
            sets.append(f"{col} = ?")
            values.append(value)

        with self._lock, self._conn:
            cursor = self._conn.execute("SELECT job_id FROM jobs WHERE job_id = ?", (job_id,))
            if cursor.fetchone() is None:
                raise KeyError(f"Job not found: {job_id}")
            if sets:
                values.append(job_id)
                self._conn.execute(f"UPDATE jobs SET {', '.join(sets)} WHERE job_id = ?", values)

        rec = self.get(job_id)
        if rec is None:
            raise KeyError(f"Job not found after update: {job_id}")
        return rec

    def get(self, job_id: str) -> Optional[JobRecord]:
        with self._lock:
            cursor = self._conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
            row = cursor.fetchone()
            return self._row_to_record(row) if row else None

    def list(self) -> List[JobRecord]:
        with self._lock:
            cursor = self._conn.execute("SELECT * FROM jobs ORDER BY created_at ASC")
            return [self._row_to_record(row) for row in cursor.fetchall()]

    def find_by_idempotency(self, task_type: str, idempotency_key: str) -> Optional[JobRecord]:
        with self._lock:
            cursor = self._conn.execute(
                """
                SELECT * FROM jobs
                WHERE task_type = ? AND idempotency_key = ?
                ORDER BY created_at DESC LIMIT 1
                """,
                (task_type, idempotency_key),
            )
            row = cursor.fetchone()
            return self._row_to_record(row) if row else None


class JobStore:
    """Job registry with JSON/SQLite backends.

    Backend selection:
    - `sqlite:///path/to/jobs.db` -> SQLite
    - `*.db` or `*.sqlite*` -> SQLite
    - other paths -> JSON
    """

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path
        self.backend_type = "json"

        if path and path.startswith("redis://"):
            self.backend_type = "redis"
            backend = _RedisJobStoreBackend(path)
            if backend.is_fallback:
                self.backend_type = "redis_fallback_json"
            self._backend: _StoreBackend = backend
        elif path and (path.startswith("sqlite:///") or path.endswith(".db") or ".sqlite" in path):
            db_path = path.removeprefix("sqlite:///") if path.startswith("sqlite:///") else path
            self.backend_type = "sqlite"
            self._backend = _SqliteJobStoreBackend(db_path)
        else:
            self._backend = _JsonJobStoreBackend(path)

    def add(self, record: JobRecord) -> None:
        self._backend.add(record)

    def update(self, job_id: str, **changes: Any) -> JobRecord:
        return self._backend.update(job_id, **changes)

    def get(self, job_id: str) -> Optional[JobRecord]:
        return self._backend.get(job_id)

    def list(self) -> List[JobRecord]:
        return self._backend.list()

    def find_by_idempotency(self, task_type: str, idempotency_key: str) -> Optional[JobRecord]:
        return self._backend.find_by_idempotency(task_type, idempotency_key)


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
        *,
        idempotency_key: Optional[str] = None,
    ) -> str:
        if idempotency_key:
            existing = self.store.find_by_idempotency(task_type, idempotency_key)
            if existing is not None:
                return existing.job_id

        job_id = str(uuid.uuid4())
        record = JobRecord(
            job_id=job_id,
            task_type=task_type,
            status="pending",
            payload=payload,
            idempotency_key=idempotency_key,
        )
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
        """Return queue and latency metrics for operational monitoring."""
        jobs = self.store.list()
        status_counter = Counter(j.status for j in jobs)
        task_counter = Counter(j.task_type for j in jobs)

        queue_delays_ms: List[float] = []
        run_durations_ms: List[float] = []
        failure_counter: Counter[str] = Counter()

        for job in jobs:
            created = _parse_ts(job.created_at)
            started = _parse_ts(job.started_at)
            finished = _parse_ts(job.finished_at)

            if created and started:
                queue_delays_ms.append((started - created).total_seconds() * 1000.0)
            if started and finished:
                run_durations_ms.append((finished - started).total_seconds() * 1000.0)
            if job.status == "failed" and job.error:
                category = str(job.error).split(":", 1)[0][:64]
                failure_counter[category] += 1

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
            "task_type_counts": dict(sorted(task_counter.items())),
            "failure_categories": dict(sorted(failure_counter.items())),
            "queue_delay_ms_p50": _safe_quantile(queue_delays_ms, 0.50),
            "queue_delay_ms_p95": _safe_quantile(queue_delays_ms, 0.95),
            "queue_delay_ms_p99": _safe_quantile(queue_delays_ms, 0.99),
            "run_duration_ms_p50": _safe_quantile(run_durations_ms, 0.50),
            "run_duration_ms_p95": _safe_quantile(run_durations_ms, 0.95),
            "run_duration_ms_p99": _safe_quantile(run_durations_ms, 0.99),
        }

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False)


# ---------------------------------------------------------------------------
# V4.0-C: Redis-compatible job store backend
# ---------------------------------------------------------------------------


class _RedisJobStoreBackend:
    """Redis-backed job store. Falls back to in-memory dict if redis is unavailable."""

    def __init__(self, url: str, ttl_seconds: int = 86400 * 7) -> None:
        self.url = url
        self.ttl_seconds = ttl_seconds
        self._redis = None
        self._fallback = _JsonJobStoreBackend(None)
        self._using_fallback = True
        try:
            import redis as redis_mod
            self._redis = redis_mod.Redis.from_url(url, decode_responses=True)
            self._redis.ping()
            self._using_fallback = False
        except Exception:
            self._redis = None
            self._using_fallback = True

    @property
    def is_fallback(self) -> bool:
        return self._using_fallback

    def add(self, record: JobRecord) -> None:
        if self._using_fallback:
            self._fallback.add(record)
            return
        data = json.dumps(asdict(record), ensure_ascii=False)
        self._redis.set(f"job:{record.job_id}", data, ex=self.ttl_seconds)
        self._redis.sadd("job:ids", record.job_id)
        if record.idempotency_key:
            self._redis.set(
                f"job:idem:{record.task_type}:{record.idempotency_key}",
                record.job_id,
                ex=self.ttl_seconds,
            )

    def update(self, job_id: str, **changes: Any) -> JobRecord:
        if self._using_fallback:
            return self._fallback.update(job_id, **changes)
        raw = self._redis.get(f"job:{job_id}")
        if raw is None:
            raise KeyError(f"Job not found: {job_id}")
        data = json.loads(raw)
        for key, value in changes.items():
            data[key] = value
        self._redis.set(f"job:{job_id}", json.dumps(data, ensure_ascii=False), ex=self.ttl_seconds)
        return JobRecord(**data)

    def get(self, job_id: str) -> Optional[JobRecord]:
        if self._using_fallback:
            return self._fallback.get(job_id)
        raw = self._redis.get(f"job:{job_id}")
        if raw is None:
            return None
        return JobRecord(**json.loads(raw))

    def list(self) -> List[JobRecord]:
        if self._using_fallback:
            return self._fallback.list()
        ids = self._redis.smembers("job:ids") or set()
        records = []
        for jid in ids:
            raw = self._redis.get(f"job:{jid}")
            if raw:
                records.append(JobRecord(**json.loads(raw)))
        return sorted(records, key=lambda r: r.created_at)

    def find_by_idempotency(self, task_type: str, idempotency_key: str) -> Optional[JobRecord]:
        if self._using_fallback:
            return self._fallback.find_by_idempotency(task_type, idempotency_key)
        jid = self._redis.get(f"job:idem:{task_type}:{idempotency_key}")
        if jid:
            return self.get(jid)
        return None
