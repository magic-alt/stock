
from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from src.platform.api_server import APIMetrics, GatewayService, MonitorService
from src.platform.demo import run_paper_trading_demo, write_demo_report
from src.platform.job_queue import JobQueue, JobStore

@pytest.fixture()
def demo_queue():
    queue = JobQueue(store=JobStore(), max_workers=1)
    try:
        yield queue
    finally:
        queue.shutdown()

def test_run_paper_trading_demo_end_to_end(demo_queue):
    report = run_paper_trading_demo(
        GatewayService(),
        queue=demo_queue,
        monitor_service=MonitorService(),
        metrics=APIMetrics(),
        limit=5,
    )

    assert report["ok"] is True
    assert report["name"] == "paper_trading_console"
    assert report["summary"]["gateway_connected"] is True
    assert report["summary"]["filled_orders"] == 1
    assert report["summary"]["cancelled_orders"] == 1
    assert report["summary"]["trades"] == 1
    assert report["summary"]["positions"] == 1
    assert report["snapshot"]["status"]["broker"] == "paper"
    assert report["monitor"]["gateway"]["status"]["connected"] is True

    step_names = [step["name"] for step in report["steps"]]
    assert step_names == [
        "connect_gateway",
        "submit_buy_limit",
        "match_buy_with_paper_price",
        "submit_exit_limit",
        "cancel_exit_limit",
        "mark_to_market",
        "collect_gateway_snapshot",
        "collect_monitor_summary",
    ]

def test_run_paper_trading_demo_rejects_bad_quantity():
    with pytest.raises(ValueError, match="quantity"):
        run_paper_trading_demo(GatewayService(), quantity=0)

def test_gateway_service_disconnect_returns_without_deadlock():
    service = GatewayService()
    service.connect({"mode": "paper", "broker": "paper"})

    result = {}

    def disconnect_gateway():
        result["status"] = service.disconnect()

    thread = threading.Thread(target=disconnect_gateway, daemon=True)
    thread.start()
    thread.join(timeout=2)

    assert not thread.is_alive()
    assert result["status"]["connected"] is False
    assert service.status()["connected"] is False

def test_write_demo_report_creates_json(tmp_path, demo_queue):
    report = run_paper_trading_demo(
        GatewayService(),
        queue=demo_queue,
        monitor_service=MonitorService(),
        metrics=APIMetrics(),
    )
    output = write_demo_report(report, tmp_path / "demo" / "paper.json")

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["summary"]["trades"] == 1

def test_demo_script_writes_report(tmp_path):
    out_path = tmp_path / "platform_console_demo.json"
    result = subprocess.run(
        [sys.executable, "scripts/demo_platform_console.py", "--out", str(out_path)],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["summary"]["trades"] == 1

