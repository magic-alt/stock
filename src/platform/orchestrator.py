"""
Workflow orchestrator for platform jobs.
"""
from __future__ import annotations

from typing import Any, Dict, List

from src.platform.backtest_task import run_backtest_job


def run_workflow(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run a sequential workflow. Example payload:
    {
      "steps": [
        {"task_type": "backtest", "payload": {...}},
        {"task_type": "backtest", "payload": {...}}
      ]
    }
    """
    steps = payload.get("steps") or []
    results: List[Dict[str, Any]] = []
    for step in steps:
        task_type = step.get("task_type")
        step_payload = step.get("payload", {})
        if task_type == "backtest":
            results.append(run_backtest_job(step_payload))
        else:
            raise ValueError(f"Unknown task_type: {task_type}")
    return {"steps": len(steps), "results": results}
