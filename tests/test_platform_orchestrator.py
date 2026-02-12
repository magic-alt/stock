import time

import pytest

from src.platform import orchestrator


def _register_temp_task(task_name, fn):
    previous = orchestrator.get_workflow_tasks().get(task_name)
    orchestrator.register_workflow_task(task_name, fn)
    return previous


def _restore_task(task_name, previous):
    if previous is None:
        orchestrator.unregister_workflow_task(task_name)
    else:
        orchestrator.register_workflow_task(task_name, previous)


def test_workflow_retry_then_success():
    attempts = {"count": 0}

    def flaky(_payload):
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise RuntimeError("boom")
        return {"ok": True}

    prev = _register_temp_task("flaky", flaky)
    try:
        result = orchestrator.run_workflow(
            {
                "retry_max": 2,
                "steps": [{"task_type": "flaky", "payload": {}}],
            }
        )
        assert result["success_steps"] == 1
        assert result["failed_steps"] == 0
        assert result["results"][0]["attempts"] == 2
    finally:
        _restore_task("flaky", prev)


def test_workflow_continue_on_failure():
    def always_fail(_payload):
        raise RuntimeError("failed")

    def always_ok(_payload):
        return {"ok": True}

    prev_fail = _register_temp_task("always_fail", always_fail)
    prev_ok = _register_temp_task("always_ok", always_ok)
    try:
        result = orchestrator.run_workflow(
            {
                "steps": [
                    {"task_type": "always_fail", "payload": {}, "on_failure": "continue"},
                    {"task_type": "always_ok", "payload": {}},
                ]
            }
        )
        assert result["steps"] == 2
        assert result["failed_steps"] == 1
        assert result["success_steps"] == 1
        assert result["results"][0]["status"] == "failed"
        assert result["results"][1]["status"] == "success"
    finally:
        _restore_task("always_fail", prev_fail)
        _restore_task("always_ok", prev_ok)


def test_workflow_abort_on_failure():
    def always_fail(_payload):
        raise RuntimeError("failed")

    prev = _register_temp_task("always_fail_abort", always_fail)
    try:
        with pytest.raises(RuntimeError):
            orchestrator.run_workflow(
                {
                    "steps": [
                        {"task_type": "always_fail_abort", "payload": {}, "on_failure": "abort"},
                    ]
                }
            )
    finally:
        _restore_task("always_fail_abort", prev)


def test_workflow_timeout():
    def sleepy(_payload):
        time.sleep(0.2)
        return {"ok": True}

    prev = _register_temp_task("sleepy", sleepy)
    try:
        with pytest.raises(RuntimeError):
            orchestrator.run_workflow(
                {
                    "steps": [
                        {
                            "task_type": "sleepy",
                            "payload": {},
                            "timeout_seconds": 0.01,
                            "on_failure": "abort",
                        }
                    ]
                }
            )
    finally:
        _restore_task("sleepy", prev)
