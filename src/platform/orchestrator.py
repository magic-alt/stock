"""
Workflow orchestrator for platform jobs.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import Any, Callable, Dict, List, Optional
import time

from src.platform.backtest_task import run_backtest_job

TaskRunner = Callable[[Dict[str, Any]], Dict[str, Any]]


_TASK_RUNNERS: Dict[str, TaskRunner] = {
    "backtest": run_backtest_job,
}


def register_workflow_task(task_type: str, runner: TaskRunner) -> None:
    """Register or override a workflow task runner."""
    _TASK_RUNNERS[str(task_type)] = runner


def unregister_workflow_task(task_type: str) -> None:
    """Unregister a workflow task runner if present."""
    _TASK_RUNNERS.pop(str(task_type), None)


def get_workflow_tasks() -> Dict[str, TaskRunner]:
    """Expose registered workflow task runners (read-only snapshot)."""
    return dict(_TASK_RUNNERS)


def _run_task_with_timeout(runner: TaskRunner, payload: Dict[str, Any], timeout_seconds: Optional[float]) -> Dict[str, Any]:
    if timeout_seconds is None or timeout_seconds <= 0:
        return runner(payload)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(runner, payload)
        try:
            return future.result(timeout=float(timeout_seconds))
        except FutureTimeout as exc:
            future.cancel()
            raise TimeoutError(f"task timeout after {timeout_seconds}s") from exc


def run_workflow(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run a sequential workflow with timeout/retry/failure-policy support.

    Example payload:
    {
      "retry_max": 1,
      "retry_backoff_seconds": 0.2,
      "timeout_seconds": 30,
      "on_failure": "abort",
      "steps": [
        {
          "name": "bt_1",
          "task_type": "backtest",
          "payload": {...},
          "retry_max": 2,
          "timeout_seconds": 120,
          "on_failure": "continue"
        }
      ]
    }

    on_failure:
      - "abort": raise RuntimeError on terminal step failure
      - "continue": record failure and continue with remaining steps
    """
    steps = payload.get("steps") or []
    defaults = {
        "retry_max": int(payload.get("retry_max", 0) or 0),
        "retry_backoff_seconds": float(payload.get("retry_backoff_seconds", 0.0) or 0.0),
        "timeout_seconds": payload.get("timeout_seconds", None),
        "on_failure": str(payload.get("on_failure", "abort") or "abort").lower(),
    }

    results: List[Dict[str, Any]] = []
    success_count = 0
    failed_count = 0

    for idx, step in enumerate(steps):
        task_type = str(step.get("task_type", "")).strip()
        step_payload = dict(step.get("payload", {}) or {})
        step_name = str(step.get("name") or f"step_{idx + 1}")

        if task_type not in _TASK_RUNNERS:
            raise ValueError(f"Unknown task_type: {task_type}")

        retry_max = int(step.get("retry_max", defaults["retry_max"]) or 0)
        backoff = float(step.get("retry_backoff_seconds", defaults["retry_backoff_seconds"]) or 0.0)
        timeout_seconds = step.get("timeout_seconds", defaults["timeout_seconds"])
        on_failure = str(step.get("on_failure", defaults["on_failure"]) or "abort").lower()

        attempt = 0
        terminal_error: Optional[str] = None
        step_result: Optional[Dict[str, Any]] = None

        while attempt <= retry_max:
            attempt += 1
            try:
                runner = _TASK_RUNNERS[task_type]
                step_result = _run_task_with_timeout(runner, step_payload, timeout_seconds)
                terminal_error = None
                break
            except Exception as exc:
                terminal_error = str(exc)
                if attempt > retry_max:
                    break
                if backoff > 0:
                    time.sleep(backoff)

        if terminal_error is None:
            success_count += 1
            results.append(
                {
                    "name": step_name,
                    "task_type": task_type,
                    "status": "success",
                    "attempts": attempt,
                    "result": step_result,
                }
            )
            continue

        failed_count += 1
        failed_payload = {
            "name": step_name,
            "task_type": task_type,
            "status": "failed",
            "attempts": attempt,
            "error": terminal_error,
        }
        results.append(failed_payload)

        if on_failure != "continue":
            raise RuntimeError(
                f"workflow step failed: name={step_name}, task_type={task_type}, "
                f"attempts={attempt}, error={terminal_error}"
            )

    return {
        "steps": len(steps),
        "success_steps": success_count,
        "failed_steps": failed_count,
        "results": results,
    }


# ---------------------------------------------------------------------------
# V4.0-C: DAG Workflow
# ---------------------------------------------------------------------------


def _topological_sort(steps: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """Sort DAG steps into execution layers (Kahn's algorithm).

    Returns a list of layers, where steps in the same layer can run in parallel.
    Raises ValueError on cycle or missing dependencies.
    """
    name_map: Dict[str, Dict[str, Any]] = {}
    for step in steps:
        name = str(step.get("name", ""))
        if not name:
            raise ValueError("DAG step missing 'name'")
        name_map[name] = step

    in_degree: Dict[str, int] = {name: 0 for name in name_map}
    dependents: Dict[str, List[str]] = {name: [] for name in name_map}

    for name, step in name_map.items():
        deps = step.get("depends_on") or []
        for dep in deps:
            if dep not in name_map:
                raise ValueError(f"DAG step '{name}' depends on unknown step '{dep}'")
            dependents[dep].append(name)
            in_degree[name] += 1

    layers: List[List[Dict[str, Any]]] = []
    ready = [name for name, deg in in_degree.items() if deg == 0]

    visited = 0
    while ready:
        layer = [name_map[n] for n in sorted(ready)]
        layers.append(layer)
        visited += len(ready)
        next_ready: List[str] = []
        for n in ready:
            for dep in dependents[n]:
                in_degree[dep] -= 1
                if in_degree[dep] == 0:
                    next_ready.append(dep)
        ready = next_ready

    if visited != len(name_map):
        raise ValueError("DAG contains a cycle")

    return layers


def run_dag_workflow(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run a DAG workflow with dependency-aware parallel execution.

    Example payload::

        {
          "max_workers": 4,
          "on_failure": "abort",
          "steps": [
            {"name": "A", "task_type": "backtest", "payload": {...}},
            {"name": "B", "task_type": "backtest", "payload": {...}, "depends_on": ["A"]},
            {"name": "C", "task_type": "backtest", "payload": {...}, "depends_on": ["A"]},
            {"name": "D", "task_type": "backtest", "payload": {...}, "depends_on": ["B", "C"]},
          ]
        }
    """
    steps = payload.get("steps") or []
    max_workers = int(payload.get("max_workers", 4) or 4)
    on_failure = str(payload.get("on_failure", "abort") or "abort").lower()

    layers = _topological_sort(steps)

    results: List[Dict[str, Any]] = []
    success_count = 0
    failed_count = 0
    aborted = False

    for layer in layers:
        if aborted:
            for step in layer:
                results.append({
                    "name": str(step.get("name", "")),
                    "task_type": str(step.get("task_type", "")),
                    "status": "skipped",
                    "error": "skipped due to earlier failure",
                })
            continue

        if len(layer) == 1:
            step = layer[0]
            r = _run_dag_step(step)
            results.append(r)
            if r["status"] == "success":
                success_count += 1
            else:
                failed_count += 1
                if on_failure != "continue":
                    aborted = True
        else:
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = {pool.submit(_run_dag_step, step): step for step in layer}
                for future in futures:
                    r = future.result()
                    results.append(r)
                    if r["status"] == "success":
                        success_count += 1
                    else:
                        failed_count += 1
                        if on_failure != "continue":
                            aborted = True

    return {
        "steps": len(steps),
        "success_steps": success_count,
        "failed_steps": failed_count,
        "results": results,
    }


def _run_dag_step(step: Dict[str, Any]) -> Dict[str, Any]:
    task_type = str(step.get("task_type", "")).strip()
    step_payload = dict(step.get("payload", {}) or {})
    step_name = str(step.get("name", ""))

    if task_type not in _TASK_RUNNERS:
        return {
            "name": step_name,
            "task_type": task_type,
            "status": "failed",
            "error": f"Unknown task_type: {task_type}",
        }

    try:
        runner = _TASK_RUNNERS[task_type]
        result = runner(step_payload)
        return {
            "name": step_name,
            "task_type": task_type,
            "status": "success",
            "result": result,
        }
    except Exception as exc:
        return {
            "name": step_name,
            "task_type": task_type,
            "status": "failed",
            "error": str(exc),
        }
