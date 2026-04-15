import json
import os
import threading
import time
import urllib.error
import urllib.request

import pytest

from src.platform.api_server import create_api_server


@pytest.fixture()
def api_runtime(tmp_path):
    audit_log_path = tmp_path / "platform_audit.log"
    server = create_api_server(
        host="127.0.0.1",
        port=0,
        job_store_path=str(tmp_path / "jobs.db"),
        max_workers=1,
        api_token="test-token",
        audit_log_path=str(audit_log_path),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    host, port = server.server_address
    base_url = f"http://{host}:{port}"

    try:
        yield {"base_url": base_url, "audit_log_path": str(audit_log_path)}
    finally:
        server.shutdown()
        server.server_close()
        server.job_queue.shutdown()  # type: ignore[attr-defined]
        thread.join(timeout=3)


def _http_request(base_url, method, path, payload=None, token=None, headers=None):
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(base_url + path, data=data, method=method)
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    for k, v in (headers or {}).items():
        req.add_header(str(k), str(v))

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            status = resp.status
            body = resp.read().decode("utf-8")
            content_type = resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        status = exc.code
        body = exc.read().decode("utf-8")
        content_type = exc.headers.get("Content-Type", "") if exc.headers else ""

    if "application/json" in content_type and body:
        return status, json.loads(body)
    return status, body


def test_api_v1_requires_bearer_token(api_runtime):
    base_url = api_runtime["base_url"]

    status, payload = _http_request(base_url, "GET", "/api/v1/jobs")
    assert status == 401
    assert payload["code"] == 40101

    status, payload = _http_request(base_url, "GET", "/api/v1/jobs", token="test-token")
    assert status == 200
    assert payload["code"] == 0
    assert "jobs" in payload["data"]


def test_api_v1_submit_and_get_workflow_job(api_runtime):
    base_url = api_runtime["base_url"]

    status, payload = _http_request(
        base_url,
        "POST",
        "/api/v1/jobs/workflow",
        payload={"steps": []},
        token="test-token",
    )
    assert status == 202
    assert payload["code"] == 0

    job_id = payload["data"]["job_id"]
    status, job_payload = _http_request(base_url, "GET", f"/api/v1/jobs/{job_id}", token="test-token")
    assert status == 200
    assert job_payload["code"] == 0
    assert job_payload["data"]["job"]["job_id"] == job_id


def test_api_v1_idempotency_key_reuses_job(api_runtime):
    base_url = api_runtime["base_url"]
    headers = {"X-Idempotency-Key": "idem-001"}

    status, payload_1 = _http_request(
        base_url,
        "POST",
        "/api/v1/jobs/workflow",
        payload={"steps": []},
        token="test-token",
        headers=headers,
    )
    assert status == 202

    status, payload_2 = _http_request(
        base_url,
        "POST",
        "/api/v1/jobs/workflow",
        payload={"steps": []},
        token="test-token",
        headers=headers,
    )
    assert status == 202
    assert payload_1["data"]["job_id"] == payload_2["data"]["job_id"]


def test_api_v1_health_metrics_and_legacy_compat(api_runtime):
    base_url = api_runtime["base_url"]

    status, payload = _http_request(base_url, "GET", "/api/v1/healthz")
    assert status == 200
    assert payload["data"]["status"] == "ok"

    status, payload = _http_request(base_url, "GET", "/api/v1/readyz")
    assert status == 200
    assert payload["data"]["status"] in {"ready", "not_ready"}

    status, payload = _http_request(
        base_url,
        "POST",
        "/api/v1/jobs/not-found/cancel",
        payload={},
        token="test-token",
    )
    assert status == 404
    assert payload["code"] == 40401

    status, legacy = _http_request(base_url, "GET", "/health")
    assert status == 200
    assert legacy["status"] == "ok"

    status, metrics = _http_request(base_url, "GET", "/metrics")
    assert status == 200
    assert "platform_api_requests_total" in metrics
    assert "platform_job_queue_delay_ms_p50" in metrics


def test_api_v1_writes_audit_records(api_runtime):
    base_url = api_runtime["base_url"]
    audit_log_path = api_runtime["audit_log_path"]

    status, payload = _http_request(
        base_url,
        "POST",
        "/api/v1/jobs/workflow",
        payload={"steps": []},
        token="test-token",
        headers={"X-Actor": "tester"},
    )
    assert status == 202
    assert payload["code"] == 0

    content = ""
    deadline = time.time() + 2.0
    while time.time() < deadline:
        if os.path.exists(audit_log_path):
            with open(audit_log_path, "r", encoding="utf-8") as fh:
                content = fh.read()
            if "job.submit" in content:
                break
        time.sleep(0.05)

    assert "job.submit" in content
    assert "tester" in content


def test_api_v1_gateway_snapshot_and_monitor_summary(api_runtime):
    base_url = api_runtime["base_url"]

    status, payload = _http_request(
        base_url,
        "POST",
        "/api/v1/gateway/connect",
        payload={"mode": "paper", "broker": "paper", "account": "paper", "initial_cash": 100000},
        token="test-token",
    )
    assert status == 200
    assert payload["data"]["gateway"]["connected"] is True

    status, payload = _http_request(
        base_url,
        "POST",
        "/api/v1/gateway/order",
        payload={
            "symbol": "600519.SH",
            "side": "buy",
            "quantity": 100,
            "price": 1800,
            "order_type": "limit",
        },
        token="test-token",
    )
    assert status == 202
    order_id = payload["data"]["order_id"]

    status, payload = _http_request(
        base_url,
        "GET",
        "/api/v1/gateway/orders?limit=5",
        token="test-token",
    )
    assert status == 200
    assert any(order["order_id"] == order_id for order in payload["data"]["orders"])

    status, payload = _http_request(
        base_url,
        "POST",
        "/api/v1/gateway/price",
        payload={"symbol": "600519.SH", "price": 1799},
        token="test-token",
    )
    assert status == 200
    assert payload["data"]["symbol"] == "600519.SH"

    status, payload = _http_request(
        base_url,
        "GET",
        "/api/v1/gateway/trades?limit=5",
        token="test-token",
    )
    assert status == 200
    assert any(trade["order_id"] == order_id for trade in payload["data"]["trades"])

    status, payload = _http_request(
        base_url,
        "GET",
        "/api/v1/gateway/snapshot?limit=5",
        token="test-token",
    )
    assert status == 200
    snapshot = payload["data"]["gateway"]
    assert snapshot["status"]["broker"] == "paper"
    assert snapshot["positions"]
    assert any(order["order_id"] == order_id for order in snapshot["orders"])

    status, payload = _http_request(
        base_url,
        "GET",
        "/api/v1/monitor/summary?limit=5",
        token="test-token",
    )
    assert status == 200
    monitor = payload["data"]["monitor"]
    assert monitor["system"] is not None
    assert monitor["gateway"]["status"]["broker"] == "paper"
    assert any(order["order_id"] == order_id for order in monitor["gateway"]["orders"])

    status, payload = _http_request(
        base_url,
        "GET",
        "/api/v1/monitor/history?limit=3",
        token="test-token",
    )
    assert status == 200
    assert isinstance(payload["data"]["history"], list)
