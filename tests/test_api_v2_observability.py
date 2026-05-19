from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from src.core.monitoring import get_metric_collector, get_tracer
from src.platform.api_v2 import create_app


def test_api_v2_propagates_request_and_trace_headers():
    get_tracer().reset()
    app = create_app(enable_cors=False)

    with TestClient(app) as client:
        response = client.get(
            "/api/v2/health",
            headers={"X-Request-ID": "req-123", "X-Trace-ID": "trace-123"},
        )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-123"
    assert response.headers["X-Trace-ID"] == "trace-123"

    spans = get_tracer().get_completed_spans()
    assert any(span["trace_id"] == "trace-123" and span["attributes"]["request_id"] == "req-123" for span in spans)
    get_tracer().reset()


def test_api_v2_metrics_prometheus_format():
    collector = get_metric_collector()
    collector.reset()
    app = create_app(enable_cors=False)

    with TestClient(app) as client:
        client.get("/api/v2/health")
        response = client.get("/api/v2/metrics?format=prometheus")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "platform_api_requests_total" in response.text
    assert "platform_job_queue_jobs_total" in response.text
    assert "platform_api_request_duration_ms_count" in response.text
    collector.reset()
