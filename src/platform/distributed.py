"""
Distributed backtest runner (local process pool).
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Any, Dict, Iterable, List

from src.platform.backtest_task import run_backtest_job


def _run_job(payload: Dict[str, Any]) -> Dict[str, Any]:
    return run_backtest_job(payload)


def run_distributed_backtests(
    payloads: Iterable[Dict[str, Any]],
    *,
    max_workers: int = 4,
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_run_job, payload) for payload in payloads]
        for future in as_completed(futures):
            results.append(future.result())
    return results
