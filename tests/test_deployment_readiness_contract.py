"""Gate 0 / PR 2 deployment correctness and readiness contract tests."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from src.platform.api_v2 import create_app


ROOT = Path(__file__).resolve().parent.parent


def _secure_runtime_paths(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PLATFORM_JOB_STORE", str(tmp_path / "jobs.json"))
    monkeypatch.setenv("MARKET_DATA_DUCKDB_PATH", str(tmp_path / "market.duckdb"))
    monkeypatch.setenv("PLATFORM_AUDIT_LOG", str(tmp_path / "audit.log"))


def _load_yaml(path: str):
    return yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))


def _container_from_deployment(deployment):
    return deployment["spec"]["template"]["spec"]["containers"][0]


def test_liveness_and_readiness_are_distinct(monkeypatch, tmp_path):
    _secure_runtime_paths(monkeypatch, tmp_path)
    app = create_app(enable_cors=False)

    with TestClient(app) as client:
        assert client.get("/api/v2/live").status_code == 200
        assert client.get("/api/v2/ready").status_code == 200

        app.state.local_market_data_initialized = False
        app.state.local_market_data_error = "simulated DuckDB startup failure"

        live = client.get("/api/v2/live")
        ready = client.get("/api/v2/ready")

    assert live.status_code == 200
    assert live.json()["alive"] is True
    assert ready.status_code == 503
    payload = ready.json()
    assert payload["ready"] is False
    assert payload["status"] == "not_ready"
    assert payload["checks"]["local_market_data"]["ready"] is False
    assert "simulated DuckDB startup failure" in payload["checks"]["local_market_data"]["detail"]


def test_readiness_reports_mandatory_dependencies(monkeypatch, tmp_path):
    _secure_runtime_paths(monkeypatch, tmp_path)
    app = create_app(enable_cors=False)

    with TestClient(app) as client:
        response = client.get("/api/v2/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert set(payload["checks"]) == {"api_auth", "job_store", "local_market_data"}
    assert all(item["ready"] for item in payload["checks"].values())
    assert payload["checks"]["job_store"]["metadata"]["backend"] == "json"


def test_readiness_fails_when_auth_is_enabled_without_token(monkeypatch, tmp_path):
    _secure_runtime_paths(monkeypatch, tmp_path)
    monkeypatch.setenv("PLATFORM_API_AUTH_DISABLED", "0")
    monkeypatch.delenv("PLATFORM_API_TOKEN", raising=False)
    app = create_app(enable_cors=False)

    with TestClient(app) as client:
        live = client.get("/api/v2/live")
        ready = client.get("/api/v2/ready")

    assert live.status_code == 200
    assert ready.status_code == 503
    auth = ready.json()["checks"]["api_auth"]
    assert auth["ready"] is False
    assert "PLATFORM_API_TOKEN" in auth["detail"]


def test_readiness_rejects_remote_job_store_fallback(monkeypatch, tmp_path):
    _secure_runtime_paths(monkeypatch, tmp_path)
    app = create_app(enable_cors=False)

    with TestClient(app) as client:
        app.state.job_queue.store.backend_type = "redis_fallback_json"
        response = client.get("/api/v2/ready")

    assert response.status_code == 503
    job_store = response.json()["checks"]["job_store"]
    assert job_store["ready"] is False
    assert job_store["metadata"]["backend"] == "redis_fallback_json"
    assert "fallback" in job_store["detail"]


def test_openapi_documents_anonymous_live_and_ready(monkeypatch, tmp_path):
    _secure_runtime_paths(monkeypatch, tmp_path)
    app = create_app(enable_cors=False)

    with TestClient(app) as client:
        schema = client.get("/api/v2/openapi.json").json()

    live = schema["paths"]["/api/v2/live"]["get"]
    ready = schema["paths"]["/api/v2/ready"]["get"]
    assert "security" not in live
    assert "security" not in ready
    assert "503" in ready["responses"]


def test_dockerfile_uses_8000_and_readiness_healthcheck():
    content = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "ENV PORT=8000" in content
    assert "EXPOSE 8000" in content
    assert 'http://localhost:${PORT}/api/v2/ready' in content
    assert "--port ${PORT}" in content
    assert "USER 10001:10001" in content


def test_compose_uses_internal_port_8000_and_readiness():
    compose = _load_yaml("docker-compose.yml")
    api = compose["services"]["api"]
    assert api["ports"] == ["${PLATFORM_HOST_PORT:-8000}:8000"]
    assert "PORT=8000" in api["environment"]
    assert "PLATFORM_API_AUTH_DISABLED=${PLATFORM_API_AUTH_DISABLED:-0}" in api["environment"]
    healthcheck = api["healthcheck"]
    assert "/api/v2/ready" in " ".join(healthcheck["test"])
    assert healthcheck["start_period"] == "10s"


def test_kubernetes_deployment_has_port_probes_resources_and_security():
    deployment = _load_yaml("deploy/k8s/platform-api-deployment.yaml")
    pod_spec = deployment["spec"]["template"]["spec"]
    container = _container_from_deployment(deployment)

    assert container["ports"] == [{"name": "http", "containerPort": 8000}]
    env = {item["name"]: item for item in container["env"]}
    assert env["PORT"]["value"] == "8000"
    assert env["PLATFORM_API_AUTH_DISABLED"]["value"] == "0"
    assert env["PLATFORM_API_TOKEN"]["valueFrom"]["secretKeyRef"] == {
        "name": "platform-api-secrets",
        "key": "api-token",
    }
    assert env["PLATFORM_JOB_STORE"]["value"].endswith("jobs.sqlite")
    assert env["MARKET_DATA_DUCKDB_PATH"]["value"].endswith("market_data.duckdb")

    assert container["livenessProbe"]["httpGet"] == {"path": "/api/v2/live", "port": "http"}
    assert container["readinessProbe"]["httpGet"] == {"path": "/api/v2/ready", "port": "http"}
    assert container["resources"]["requests"]["cpu"] == "250m"
    assert container["resources"]["requests"]["memory"] == "512Mi"
    assert container["resources"]["limits"]["memory"] == "2Gi"

    assert pod_spec["securityContext"]["runAsNonRoot"] is True
    assert pod_spec["securityContext"]["runAsUser"] == 10001
    assert pod_spec["securityContext"]["seccompProfile"]["type"] == "RuntimeDefault"
    assert container["securityContext"]["allowPrivilegeEscalation"] is False
    assert container["securityContext"]["capabilities"]["drop"] == ["ALL"]


def test_kubernetes_service_targets_named_8000_port():
    service = _load_yaml("deploy/k8s/platform-api-service.yaml")
    port = service["spec"]["ports"][0]
    assert port["port"] == 8000
    assert port["targetPort"] == "http"


def test_kubernetes_secret_example_matches_deployment_contract():
    secret = _load_yaml("deploy/k8s/platform-api-secret.example.yaml")
    assert secret["metadata"]["name"] == "platform-api-secrets"
    assert "api-token" in secret["stringData"]
    assert secret["stringData"]["api-token"].startswith("replace-")


def test_render_and_release_script_gate_on_readiness():
    render = _load_yaml("render.yaml")
    assert render["services"][0]["healthCheckPath"] == "/api/v2/ready"

    script = (ROOT / "scripts" / "deploy_release.py").read_text(encoding="utf-8")
    assert 'default="http://127.0.0.1:8000/api/v2/ready"' in script
    assert "200 <= resp.status < 400" in script
