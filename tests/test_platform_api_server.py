import json
import threading
import urllib.error
import urllib.request

import pytest

from src.platform.api_server import create_api_server


@pytest.fixture()
def api_base_url(tmp_path):
    server = create_api_server(
        host="127.0.0.1",
        port=0,
        job_store_path=str(tmp_path / "jobs.json"),
        max_workers=1,
        api_token="test-token",
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    host, port = server.server_address
    base_url = f"http://{host}:{port}"

    try:
        yield base_url
    finally:
        server.shutdown()
        server.server_close()
        server.job_queue.shutdown()  # type: ignore[attr-defined]
        thread.join(timeout=3)


def _http_request(base_url, method, path, payload=None, token=None):
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(base_url + path, data=data, method=method)
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")

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


def test_api_v1_requires_bearer_token(api_base_url):
    status, payload = _http_request(api_base_url, "GET", "/api/v1/jobs")
    assert status == 401
    assert payload["code"] == 40101

    status, payload = _http_request(api_base_url, "GET", "/api/v1/jobs", token="test-token")
    assert status == 200
    assert payload["code"] == 0
    assert "jobs" in payload["data"]


def test_api_v1_submit_and_get_workflow_job(api_base_url):
    status, payload = _http_request(
        api_base_url,
        "POST",
        "/api/v1/jobs/workflow",
        payload={"steps": []},
        token="test-token",
    )
    assert status == 202
    assert payload["code"] == 0

    job_id = payload["data"]["job_id"]
    status, job_payload = _http_request(api_base_url, "GET", f"/api/v1/jobs/{job_id}", token="test-token")
    assert status == 200
    assert job_payload["code"] == 0
    assert job_payload["data"]["job"]["job_id"] == job_id


def test_api_v1_health_metrics_and_legacy_compat(api_base_url):
    status, payload = _http_request(api_base_url, "GET", "/api/v1/healthz")
    assert status == 200
    assert payload["data"]["status"] == "ok"

    status, payload = _http_request(api_base_url, "GET", "/api/v1/readyz")
    assert status == 200
    assert payload["data"]["status"] in {"ready", "not_ready"}

    status, payload = _http_request(
        api_base_url,
        "POST",
        "/api/v1/jobs/not-found/cancel",
        payload={},
        token="test-token",
    )
    assert status == 404
    assert payload["code"] == 40401

    status, legacy = _http_request(api_base_url, "GET", "/health")
    assert status == 200
    assert legacy["status"] == "ok"

    status, metrics = _http_request(api_base_url, "GET", "/metrics")
    assert status == 200
    assert "platform_api_requests_total" in metrics
