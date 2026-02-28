"""
Platform benchmark helper.

Runs synthetic queue workloads and exports baseline metrics for trend tracking.
Supports historical baseline storage and automatic regression detection.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.platform.job_queue import JobQueue, JobStore


# ---------------------------------------------------------------------------
# Performance thresholds (from PERFORMANCE_BENCHMARK_SPEC.md)
# ---------------------------------------------------------------------------

THRESHOLDS: Dict[str, Any] = {
    # Parallel scenario error rate must be < 1%
    "max_error_rate": 0.01,
    # Regression > 15% on any core metric triggers block
    "regression_limit_pct": 0.15,
    # Core metrics monitored for regression
    "regression_metrics": [
        "throughput_jobs_per_sec",
        "queue_metrics.queue_delay_ms_p95",
        "queue_metrics.run_duration_ms_p95",
    ],
}


def _worker(payload: Dict[str, Any]) -> Dict[str, Any]:
    sleep_ms = float(payload.get("sleep_ms", 10.0))
    time.sleep(max(0.0, sleep_ms) / 1000.0)
    return {"ok": True, "sleep_ms": sleep_ms}


def run_benchmark(*, jobs: int, workers: int, sleep_ms: float) -> Dict[str, Any]:
    import tempfile

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
    failed = [r for r in finished if r and r.status == "failed"]
    throughput = len(ok) / elapsed if elapsed > 0 else 0.0
    error_rate = len(failed) / len(finished) if finished else 0.0

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "jobs": jobs,
        "workers": workers,
        "sleep_ms": sleep_ms,
        "elapsed_seconds": round(elapsed, 4),
        "throughput_jobs_per_sec": round(throughput, 4),
        "success_jobs": len(ok),
        "failed_jobs": len(failed),
        "error_rate": round(error_rate, 6),
        "queue_metrics": metrics,
    }


# ---------------------------------------------------------------------------
# Threshold assertions
# ---------------------------------------------------------------------------

def check_thresholds(result: Dict[str, Any]) -> List[str]:
    """Return list of threshold violations (empty = all pass)."""
    violations: List[str] = []
    error_rate = result.get("error_rate", 0.0)
    max_err = THRESHOLDS["max_error_rate"]
    if error_rate > max_err:
        violations.append(
            f"error_rate {error_rate:.4f} exceeds threshold {max_err}"
        )
    return violations


# ---------------------------------------------------------------------------
# Baseline storage & regression detection
# ---------------------------------------------------------------------------

_DEFAULT_BASELINE_DIR = os.path.join("cache", "benchmark_baselines")


def _get_nested(d: Dict, dotted_key: str) -> Optional[float]:
    """Resolve dotted key like 'queue_metrics.queue_delay_ms_p95'."""
    parts = dotted_key.split(".")
    cur: Any = d
    for p in parts:
        if isinstance(cur, dict):
            cur = cur.get(p)
        else:
            return None
    return float(cur) if cur is not None else None


def save_baseline(result: Dict[str, Any], baseline_dir: Optional[str] = None) -> str:
    """Persist benchmark result as a baseline file. Returns path."""
    bdir = baseline_dir or _DEFAULT_BASELINE_DIR
    os.makedirs(bdir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(bdir, f"baseline_{ts}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    return path


def load_latest_baseline(baseline_dir: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Load most recent baseline file, or None."""
    bdir = baseline_dir or _DEFAULT_BASELINE_DIR
    if not os.path.isdir(bdir):
        return None
    files = sorted(
        [f for f in os.listdir(bdir) if f.startswith("baseline_") and f.endswith(".json")],
        reverse=True,
    )
    if not files:
        return None
    with open(os.path.join(bdir, files[0]), "r", encoding="utf-8") as fh:
        return json.load(fh)


def detect_regression(
    current: Dict[str, Any],
    baseline: Dict[str, Any],
    limit_pct: Optional[float] = None,
) -> List[str]:
    """
    Compare current run against baseline.

    Returns list of regression warnings.  Empty list means no regression.
    For latency metrics (containing 'delay' or 'duration'), an *increase* is
    regression.  For throughput, a *decrease* is regression.
    """
    limit = limit_pct if limit_pct is not None else THRESHOLDS["regression_limit_pct"]
    warnings: List[str] = []

    for metric_key in THRESHOLDS["regression_metrics"]:
        cur_val = _get_nested(current, metric_key)
        base_val = _get_nested(baseline, metric_key)
        if cur_val is None or base_val is None or base_val == 0:
            continue

        # For latency metrics, higher is worse; for throughput, lower is worse
        is_latency = any(tag in metric_key for tag in ("delay", "duration"))
        if is_latency:
            change = (cur_val - base_val) / abs(base_val)
            if change > limit:
                warnings.append(
                    f"REGRESSION {metric_key}: {base_val:.4f} -> {cur_val:.4f} "
                    f"(+{change*100:.1f}%, limit {limit*100:.0f}%)"
                )
        else:
            change = (base_val - cur_val) / abs(base_val)
            if change > limit:
                warnings.append(
                    f"REGRESSION {metric_key}: {base_val:.4f} -> {cur_val:.4f} "
                    f"(-{change*100:.1f}%, limit {limit*100:.0f}%)"
                )

    return warnings


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run synthetic platform benchmark")
    parser.add_argument("--jobs", type=int, default=100)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--sleep-ms", type=float, default=10.0)
    parser.add_argument("--out", default=None, help="Optional JSON output path")
    parser.add_argument(
        "--save-baseline", action="store_true",
        help="Save result as new baseline"
    )
    parser.add_argument(
        "--check-regression", action="store_true",
        help="Compare against latest baseline and report regressions"
    )
    parser.add_argument(
        "--check-thresholds", action="store_true",
        help="Assert performance thresholds (non-zero exit on violation)"
    )
    parser.add_argument("--baseline-dir", default=None, help="Baseline storage directory")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_benchmark(jobs=args.jobs, workers=args.workers, sleep_ms=args.sleep_ms)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, ensure_ascii=False, indent=2, default=str)

    exit_code = 0

    # Threshold assertions
    if args.check_thresholds:
        violations = check_thresholds(result)
        if violations:
            print("\n=== THRESHOLD VIOLATIONS ===")
            for v in violations:
                print(f"  FAIL: {v}")
            exit_code = 1
        else:
            print("\n=== All thresholds passed ===")

    # Baseline save / regression
    if args.save_baseline:
        path = save_baseline(result, args.baseline_dir)
        print(f"\nBaseline saved: {path}")

    if args.check_regression:
        baseline = load_latest_baseline(args.baseline_dir)
        if baseline is None:
            print("\nNo baseline found – skipping regression check.")
        else:
            regressions = detect_regression(result, baseline)
            if regressions:
                print("\n=== REGRESSION DETECTED ===")
                for r in regressions:
                    print(f"  WARN: {r}")
                exit_code = 1
            else:
                print("\n=== No regression detected ===")

    if exit_code:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
