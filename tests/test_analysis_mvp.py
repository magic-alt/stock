from __future__ import annotations

import time
from pathlib import Path

import pytest

from src.platform.analysis_service import AnalysisRequestPayload, StockAnalysisService


def test_stock_analysis_service_runs_with_sample_data(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    service = StockAnalysisService()

    result = service.analyze(
        AnalysisRequestPayload(
            symbol="600519.SH",
            source="sample",
            days=60,
            include_backtest=True,
            use_ai=True,
        )
    )

    assert result["symbol"] == "600519.SH"
    assert result["data_quality"]["source"] == "sample"
    assert result["signal"]["rating"] in {"buy", "watch", "sell"}
    assert 0 <= result["signal"]["score"] <= 100
    assert result["backtest_preview"]["enabled"] is True
    assert result["ai_summary"]["status"] == "missing_api_key"
    assert "Stock Analysis: 600519.SH" in result["markdown_report"]


def test_stock_analysis_auto_falls_back_to_sample(monkeypatch):
    class BrokenProvider:
        def load_stock_daily(self, symbols, start, end):
            raise RuntimeError("network unavailable")

    monkeypatch.setattr("src.data_sources.providers.get_provider", lambda source: BrokenProvider())

    result = StockAnalysisService().analyze(AnalysisRequestPayload(symbol="600519.SH", source="auto"))

    assert result["data_quality"]["source"] == "sample"
    assert any("fell back" in item for item in result["data_quality"]["warnings"])


def test_analysis_capabilities_include_sample_symbols():
    capabilities = StockAnalysisService().capabilities()

    assert "sample" in capabilities["sources"]
    assert "600519.SH" in capabilities["sample_symbols"]
    assert capabilities["default_source"] == "sample"


def test_api_v2_default_cors_allows_localhost_and_loopback():
    pytest.importorskip("fastapi")
    from src.platform.api_v2 import create_app

    app = create_app(enable_cors=True)
    cors = next(m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware")

    assert "http://localhost:3000" in cors.kwargs["allow_origins"]
    assert "http://127.0.0.1:3000" in cors.kwargs["allow_origins"]


@pytest.fixture
def client(monkeypatch, tmp_path: Path):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from src.platform.api_v2 import create_app

    monkeypatch.setenv("PLATFORM_JOB_STORE", str(tmp_path / "jobs.json"))
    app = create_app(enable_cors=False)
    with TestClient(app) as test_client:
        yield test_client


def test_analysis_run_endpoint(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    resp = client.post(
        "/api/v2/analysis/run",
        json={"symbol": "600519.SH", "source": "sample", "days": 60, "use_ai": True},
    )

    assert resp.status_code == 200
    body = resp.json()
    analysis = body["data"]["analysis"]
    assert analysis["symbol"] == "600519.SH"
    assert analysis["data_quality"]["source"] == "sample"
    assert analysis["ai_summary"]["status"] == "missing_api_key"


def test_analysis_job_endpoint(client):
    resp = client.post(
        "/api/v2/analysis/jobs",
        json={"symbol": "600519.SH", "source": "sample", "days": 60},
    )
    assert resp.status_code == 200
    job_id = resp.json()["data"]["job_id"]

    job = None
    for _ in range(20):
        job_resp = client.get(f"/api/v2/analysis/jobs/{job_id}")
        assert job_resp.status_code == 200
        job = job_resp.json()["data"]["job"]
        if job["status"] == "success":
            break
        time.sleep(0.05)

    assert job is not None
    assert job["status"] == "success"
    assert job["result"]["symbol"] == "600519.SH"

    list_resp = client.get("/api/v2/analysis/jobs?limit=5")
    assert list_resp.status_code == 200
    assert any(item["job_id"] == job_id for item in list_resp.json()["data"]["jobs"])


def test_analysis_run_endpoint_rejects_unknown_symbol(client):
    resp = client.post("/api/v2/analysis/run", json={"symbol": "NOPE", "source": "sample"})

    assert resp.status_code == 404
