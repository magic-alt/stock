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


# ---------------------------------------------------------------------------
# DAG Workflow tests (V4.0-C)
# ---------------------------------------------------------------------------

from src.platform.orchestrator import run_dag_workflow


def test_dag_linear_dependency():
    """A -> B -> C linear chain."""
    order = []

    def task_fn(_payload):
        order.append(_payload.get("name"))
        return {"ok": True}

    prev = _register_temp_task("dag_task", task_fn)
    try:
        result = run_dag_workflow({
            "steps": [
                {"name": "A", "task_type": "dag_task", "payload": {"name": "A"}},
                {"name": "B", "task_type": "dag_task", "payload": {"name": "B"}, "depends_on": ["A"]},
                {"name": "C", "task_type": "dag_task", "payload": {"name": "C"}, "depends_on": ["B"]},
            ]
        })
        assert result["success_steps"] == 3
        assert result["failed_steps"] == 0
        # Verify ordering: A before B before C
        assert order.index("A") < order.index("B") < order.index("C")
    finally:
        _restore_task("dag_task", prev)


def test_dag_parallel_independent():
    """A, B independent -> C depends on both."""
    def ok_task(_payload):
        return {"ok": True}

    prev = _register_temp_task("par_task", ok_task)
    try:
        result = run_dag_workflow({
            "steps": [
                {"name": "A", "task_type": "par_task", "payload": {}},
                {"name": "B", "task_type": "par_task", "payload": {}},
                {"name": "C", "task_type": "par_task", "payload": {}, "depends_on": ["A", "B"]},
            ]
        })
        assert result["success_steps"] == 3
    finally:
        _restore_task("par_task", prev)


def test_dag_diamond_dependency():
    """A -> B,C -> D diamond pattern."""
    def ok_task(_payload):
        return {"ok": True}

    prev = _register_temp_task("diamond_task", ok_task)
    try:
        result = run_dag_workflow({
            "steps": [
                {"name": "A", "task_type": "diamond_task", "payload": {}},
                {"name": "B", "task_type": "diamond_task", "payload": {}, "depends_on": ["A"]},
                {"name": "C", "task_type": "diamond_task", "payload": {}, "depends_on": ["A"]},
                {"name": "D", "task_type": "diamond_task", "payload": {}, "depends_on": ["B", "C"]},
            ]
        })
        assert result["success_steps"] == 4
    finally:
        _restore_task("diamond_task", prev)


def test_dag_cycle_detection_raises():
    def ok_task(_payload):
        return {"ok": True}

    prev = _register_temp_task("cycle_task", ok_task)
    try:
        with pytest.raises(ValueError, match="cycle"):
            run_dag_workflow({
                "steps": [
                    {"name": "A", "task_type": "cycle_task", "payload": {}, "depends_on": ["B"]},
                    {"name": "B", "task_type": "cycle_task", "payload": {}, "depends_on": ["A"]},
                ]
            })
    finally:
        _restore_task("cycle_task", prev)


def test_dag_missing_dependency_raises():
    def ok_task(_payload):
        return {"ok": True}

    prev = _register_temp_task("miss_task", ok_task)
    try:
        with pytest.raises(ValueError, match="unknown step"):
            run_dag_workflow({
                "steps": [
                    {"name": "A", "task_type": "miss_task", "payload": {}, "depends_on": ["Z"]},
                ]
            })
    finally:
        _restore_task("miss_task", prev)


def test_dag_step_failure_abort():
    def fail_task(_payload):
        raise RuntimeError("boom")

    def ok_task(_payload):
        return {"ok": True}

    prev_f = _register_temp_task("dag_fail", fail_task)
    prev_o = _register_temp_task("dag_ok", ok_task)
    try:
        result = run_dag_workflow({
            "on_failure": "abort",
            "steps": [
                {"name": "A", "task_type": "dag_ok", "payload": {}},
                {"name": "B", "task_type": "dag_fail", "payload": {}, "depends_on": ["A"]},
                {"name": "C", "task_type": "dag_ok", "payload": {}, "depends_on": ["B"]},
            ]
        })
        assert result["failed_steps"] >= 1
        statuses = {r["name"]: r["status"] for r in result["results"]}
        assert statuses["B"] == "failed"
        assert statuses["C"] == "skipped"
    finally:
        _restore_task("dag_fail", prev_f)
        _restore_task("dag_ok", prev_o)


def test_dag_step_failure_continue():
    def fail_task(_payload):
        raise RuntimeError("boom")

    def ok_task(_payload):
        return {"ok": True}

    prev_f = _register_temp_task("dag_fail_c", fail_task)
    prev_o = _register_temp_task("dag_ok_c", ok_task)
    try:
        result = run_dag_workflow({
            "on_failure": "continue",
            "steps": [
                {"name": "A", "task_type": "dag_ok_c", "payload": {}},
                {"name": "B", "task_type": "dag_fail_c", "payload": {}, "depends_on": ["A"]},
                {"name": "C", "task_type": "dag_ok_c", "payload": {}, "depends_on": ["A"]},
            ]
        })
        statuses = {r["name"]: r["status"] for r in result["results"]}
        assert statuses["A"] == "success"
        assert statuses["B"] == "failed"
        assert statuses["C"] == "success"
    finally:
        _restore_task("dag_fail_c", prev_f)
        _restore_task("dag_ok_c", prev_o)
