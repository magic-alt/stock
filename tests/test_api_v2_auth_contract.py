"""Gate 0 contract tests for FastAPI v2 authentication and authorization."""
from __future__ import annotations

import json

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from src.core.auth import Role
from src.platform.api_v2 import create_app


TOKEN = "gate0-test-token"


def _configure_secure_app(
    monkeypatch,
    tmp_path,
    *,
    role: str = Role.ADMIN,
    token: str = TOKEN,
    subject: str | None = None,
):
    audit_path = tmp_path / f"audit-{role}.log"
    monkeypatch.setenv("PLATFORM_API_AUTH_DISABLED", "0")
    monkeypatch.setenv("PLATFORM_API_TOKEN", token)
    monkeypatch.setenv("PLATFORM_API_TOKEN_SUBJECT", subject or f"test-{role}")
    monkeypatch.setenv("PLATFORM_API_TOKEN_ROLE", role)
    monkeypatch.setenv("PLATFORM_AUDIT_LOG", str(audit_path))
    monkeypatch.setenv("PLATFORM_JOB_STORE", str(tmp_path / f"jobs-{role}.json"))
    return create_app(enable_cors=False), audit_path


def _auth_headers(token: str = TOKEN):
    return {"Authorization": f"Bearer {token}"}


def test_health_remains_anonymous(monkeypatch, tmp_path):
    app, _ = _configure_secure_app(monkeypatch, tmp_path)
    with TestClient(app) as client:
        response = client.get("/api/v2/health")
    assert response.status_code == 200


def test_missing_bearer_token_returns_401(monkeypatch, tmp_path):
    app, _ = _configure_secure_app(monkeypatch, tmp_path)
    with TestClient(app) as client:
        response = client.post(
            "/api/v2/gateway/order",
            json={"symbol": "600519.SH", "side": "buy", "quantity": 100, "price": 100.0},
        )
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json()["detail"] == "Not authenticated"


def test_malformed_authorization_header_returns_401(monkeypatch, tmp_path):
    app, _ = _configure_secure_app(monkeypatch, tmp_path)
    with TestClient(app) as client:
        response = client.post(
            "/api/v2/accounts",
            headers={"Authorization": "Basic abc123"},
            json={"account_group": "default", "owner_id": "test", "initial_cash": 1000},
        )
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_invalid_bearer_token_returns_401(monkeypatch, tmp_path):
    app, _ = _configure_secure_app(monkeypatch, tmp_path)
    with TestClient(app) as client:
        response = client.post(
            "/api/v2/accounts",
            headers=_auth_headers("wrong-token"),
            json={"account_group": "default", "owner_id": "test", "initial_cash": 1000},
        )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid authentication credentials"


def test_enabled_auth_without_server_token_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setenv("PLATFORM_API_AUTH_DISABLED", "0")
    monkeypatch.delenv("PLATFORM_API_TOKEN", raising=False)
    monkeypatch.setenv("PLATFORM_AUDIT_LOG", str(tmp_path / "missing-token-audit.log"))
    monkeypatch.setenv("PLATFORM_JOB_STORE", str(tmp_path / "missing-token-jobs.json"))
    app = create_app(enable_cors=False)

    with TestClient(app) as client:
        health = client.get("/api/v2/health")
        protected = client.post(
            "/api/v2/accounts",
            json={"account_group": "default", "owner_id": "test", "initial_cash": 1000},
        )

    assert health.status_code == 200
    assert protected.status_code == 503
    assert "PLATFORM_API_TOKEN" in protected.json()["detail"]


def test_authenticated_viewer_is_forbidden_from_account_mutation(monkeypatch, tmp_path):
    app, _ = _configure_secure_app(monkeypatch, tmp_path, role=Role.VIEWER)
    with TestClient(app) as client:
        response = client.post(
            "/api/v2/accounts",
            headers=_auth_headers(),
            json={"account_group": "default", "owner_id": "test", "initial_cash": 1000},
        )
    assert response.status_code == 403
    assert response.json()["detail"] == "Forbidden"


def test_authenticated_viewer_can_use_authorized_read_surface(monkeypatch, tmp_path):
    app, _ = _configure_secure_app(monkeypatch, tmp_path, role=Role.VIEWER)
    with TestClient(app) as client:
        response = client.get("/api/v2/gateway/status", headers=_auth_headers())
    assert response.status_code == 200
    assert response.json()["data"]["gateway"]["connected"] is False


def test_admin_token_reaches_protected_mutation(monkeypatch, tmp_path):
    app, _ = _configure_secure_app(monkeypatch, tmp_path, role=Role.ADMIN)
    with TestClient(app) as client:
        response = client.post(
            "/api/v2/accounts",
            headers=_auth_headers(),
            json={"account_group": "gate0", "owner_id": "owner", "initial_cash": 1000},
        )
    assert response.status_code == 200
    account = response.json()["data"]["account"]
    assert account["account_group"] == "gate0"
    assert account["owner_id"] == "owner"


def test_subject_is_propagated_to_hash_chain_audit(monkeypatch, tmp_path):
    app, audit_path = _configure_secure_app(
        monkeypatch,
        tmp_path,
        role=Role.ADMIN,
        subject="operator-42",
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v2/accounts",
            headers=_auth_headers(),
            json={"account_group": "gate0", "owner_id": "owner", "initial_cash": 1000},
        )
    assert response.status_code == 200

    records = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert records
    event = records[-1]
    assert event["actor"] == "operator-42"
    assert event["action"] == "account.create"
    assert event["result"] == "success"
    assert event["details"]["permission"] == "account.manage"
    assert event["hash"]


def test_denied_request_is_audited(monkeypatch, tmp_path):
    app, audit_path = _configure_secure_app(monkeypatch, tmp_path, role=Role.VIEWER)
    with TestClient(app) as client:
        response = client.post(
            "/api/v2/accounts",
            headers=_auth_headers(),
            json={"account_group": "gate0", "owner_id": "owner", "initial_cash": 1000},
        )
    assert response.status_code == 403

    records = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert records[-1]["actor"] == "test-viewer"
    assert records[-1]["result"] == "denied"
    assert "Permission denied" in records[-1]["details"]["reason"]


def test_openapi_documents_bearer_security(monkeypatch, tmp_path):
    app, _ = _configure_secure_app(monkeypatch, tmp_path)
    with TestClient(app) as client:
        schema = client.get("/api/v2/openapi.json").json()

    scheme = schema["components"]["securitySchemes"]["BearerAuth"]
    assert scheme["type"] == "http"
    assert scheme["scheme"] == "bearer"
    assert schema["paths"]["/api/v2/gateway/order"]["post"]["security"] == [{"BearerAuth": []}]
    assert "401" in schema["paths"]["/api/v2/gateway/order"]["post"]["responses"]
    assert "403" in schema["paths"]["/api/v2/gateway/order"]["post"]["responses"]
    assert "security" not in schema["paths"]["/api/v2/health"]["get"]


def test_explicit_local_development_override(monkeypatch, tmp_path):
    monkeypatch.setenv("PLATFORM_API_AUTH_DISABLED", "1")
    monkeypatch.delenv("PLATFORM_API_TOKEN", raising=False)
    audit_path = tmp_path / "local-dev-audit.log"
    monkeypatch.setenv("PLATFORM_AUDIT_LOG", str(audit_path))
    monkeypatch.setenv("PLATFORM_JOB_STORE", str(tmp_path / "local-dev-jobs.json"))
    app = create_app(enable_cors=False)

    with TestClient(app) as client:
        response = client.post(
            "/api/v2/accounts",
            json={"account_group": "local", "owner_id": "dev", "initial_cash": 1000},
        )

    assert response.status_code == 200
    records = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert records[-1]["actor"] == "local-dev"
    assert records[-1]["details"]["reason"] == "auth_disabled_local_dev"
