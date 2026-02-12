"""
Platform benchmark helper.

Runs synthetic queue workloads and exports baseline metrics for trend tracking.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import tempfile
import time
from typing import Any, Dict, List

from src.platform.job_queue import JobQueue, JobStore


def _worker(payload: Dict[str, Any]) -> Dict[str, Any]:
    sleep_ms = float(payload.get("sleep_ms", 10.0))
    time.sleep(max(0.0, sleep_ms) / 1000.0)
    return {"ok": True, "sleep_ms": sleep_ms}


def run_benchmark(*, jobs: int, workers: int, sleep_ms: float) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="platform_bench_") as tmp:
        store = JobStore(path=os.path.join(tmp, "bench_jobs.db"))
        queue = JobQueue(store=store, max_workers=workers)
        start = time.perf_counter()
        submitted: List[str] = []
        for _ in range(jobs):
            submitted.append(queue.submit("benchmark", _worker, {"sleep_ms": sleep_ms}))

        finished = []
        for job_id in submitted:
            rec = queue.wait(job_id, timeout=max(5.0, sleep_ms / 1000.0 * jobs * 2))
            finished.append(rec)

        elapsed = time.perf_counter() - start
        metrics = queue.metrics()
        queue.shutdown()

    ok = [r for r in finished if r and r.status == "success"]
    throughput = len(ok) / elapsed if elapsed > 0 else 0.0

    return {
        "jobs": jobs,
        "workers": workers,
        "sleep_ms": sleep_ms,
        "elapsed_seconds": elapsed,
        "throughput_jobs_per_sec": throughput,
        "success_jobs": len(ok),
        "queue_metrics": metrics,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run synthetic platform benchmark")
    parser.add_argument("--jobs", type=int, default=100)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--sleep-ms", type=float, default=10.0)
    parser.add_argument("--out", default=None, help="Optional JSON output path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_benchmark(jobs=args.jobs, workers=args.workers, sleep_ms=args.sleep_ms)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
