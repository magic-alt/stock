from __future__ import annotations

import json
import time
import math
from pathlib import Path

import pandas as pd
import pytest

from src.platform.analysis_service import AnalysisRequestPayload, StockAnalysisService


def _ohlcv_frame(rows: int = 80, close_offset: float = 0.0) -> pd.DataFrame:
    index = pd.bdate_range("2024-01-02", periods=rows)
    close = pd.Series(
        [10 + idx * 0.03 + math.sin(idx / 4) * 0.6 + close_offset for idx in range(rows)],
        index=index,
        dtype=float,
    )
    return pd.DataFrame(
        {
            "open": close - 0.1,
            "high": close + 0.3,
            "low": close - 0.3,
            "close": close,
            "volume": 1_000_000 + close * 1000,
        },
        index=index,
    )


class FakeProvider:
    def __init__(self, frame: pd.DataFrame | None = None):
        self.frame = frame if frame is not None else _ohlcv_frame()

    def load_stock_daily(self, symbols, start, end, **kwargs):
        return {symbols[0]: self.frame}


def test_stock_analysis_service_runs_with_real_provider_data(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("src.data_sources.providers.get_provider", lambda source: FakeProvider())
    service = StockAnalysisService()

    result = service.analyze(
        AnalysisRequestPayload(
            symbol="60036",
            source="eastmoney",
            days=60,
            include_backtest=True,
            use_ai=True,
        )
    )

    assert result["symbol"] == "600036.SH"
    assert result["data_quality"]["source"] == "eastmoney"
    assert result["signal"]["rating"] in {"buy", "watch", "sell"}
    assert 0 <= result["signal"]["score"] <= 100
    assert result["backtest_preview"]["enabled"] is True
    assert result["ai_summary"]["status"] == "missing_api_key"
    assert "Stock Analysis: 600036.SH" in result["markdown_report"]


def test_stock_analysis_signal_messages_include_selected_symbol(monkeypatch):
    monkeypatch.setattr("src.data_sources.providers.get_provider", lambda source: FakeProvider())

    result = StockAnalysisService().analyze(
        AnalysisRequestPayload(
            symbol="600519.SH",
            source="eastmoney",
            days=60,
            include_backtest=False,
        )
    )

    messages = result["signal"]["reasons"] + result["signal"]["risks"]
    assert messages
    assert all("600519.SH" in message for message in messages)
    assert any(any(char.isdigit() for char in message) for message in messages)


def test_stock_analysis_auto_tries_real_provider_order(monkeypatch):
    calls = []

    def fake_get_provider(source):
        calls.append(source)
        offsets = {"akshare": 0.0, "sina": 0.01, "tencent": -0.01}
        return FakeProvider(_ohlcv_frame(close_offset=offsets[source]))

    monkeypatch.setattr("src.data_sources.providers.get_provider", fake_get_provider)

    result = StockAnalysisService().analyze(AnalysisRequestPayload(symbol="600036SH", source="auto"))

    assert result["symbol"] == "600036.SH"
    assert result["data_quality"]["source"] == "akshare"
    assert result["data_quality"]["validation_status"] == "verified"
    assert set(result["data_quality"]["validated_sources"]) == {"akshare", "sina", "tencent"}
    assert set(calls) == {"akshare", "sina", "tencent"}


def test_stock_analysis_auto_prefers_broader_verified_coverage(monkeypatch):
    short_frame = _ohlcv_frame(rows=40, close_offset=0.0)
    long_frame = _ohlcv_frame(rows=260, close_offset=0.0)

    def fake_get_provider(source):
        if source == "akshare":
            return FakeProvider(short_frame)
        return FakeProvider(long_frame)

    monkeypatch.setattr("src.data_sources.providers.get_provider", fake_get_provider)

    result = StockAnalysisService().analyze(AnalysisRequestPayload(symbol="600036.SH", source="auto", days=120))

    assert result["data_quality"]["source"] == "sina"
    assert result["data_quality"]["validation_status"] == "verified"
    assert any("broader or newer" in item for item in result["data_quality"]["warnings"])


def test_verified_history_gateway_loads_auto_range_from_complete_source(monkeypatch):
    short_frame = _ohlcv_frame(rows=40, close_offset=0.0)
    long_frame = _ohlcv_frame(rows=260, close_offset=0.0)

    def fake_get_provider(source, **kwargs):
        if source == "akshare":
            return FakeProvider(short_frame)
        return FakeProvider(long_frame)

    monkeypatch.setattr("src.data_sources.providers.get_provider", fake_get_provider)

    from src.platform.verified_history_gateway import VerifiedHistoryGateway

    gateway = VerifiedHistoryGateway(source="auto")
    data = gateway.load_bars(["600036.SH"], "2024-01-01", "2024-12-31")

    assert len(data["600036.SH"]) == 260
    assert gateway.data_quality["600036.SH"]["source"] == "sina"


def test_analysis_capabilities_expose_real_sources_only():
    capabilities = StockAnalysisService().capabilities()

    assert "sample" not in capabilities["sources"]
    assert "akshare" in capabilities["sources"]
    assert "sina" in capabilities["sources"]
    assert "tencent" in capabilities["sources"]
    assert "eastmoney" in capabilities["sources"]
    assert capabilities["default_source"] == "auto"


def test_analysis_ai_summary_uses_configured_openai_compatible_settings(monkeypatch):
    from src.core.config import AIConfig, ConfigManager, GlobalConfig, set_config

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    set_config(
        ConfigManager(
            config=GlobalConfig(
                ai=AIConfig(
                    api_key="cfg-key",
                    base_url="https://llm.example.test/v1",
                    model="stock-model",
                    timeout_seconds=3,
                )
            )
        )
    )

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({"choices": [{"message": {"content": "configured summary"}}]}).encode("utf-8")

    def fake_urlopen(request, timeout):
        assert request.full_url == "https://llm.example.test/v1/chat/completions"
        assert request.get_header("Authorization") == "Bearer cfg-key"
        assert timeout == 3
        return FakeResponse()

    try:
        monkeypatch.setattr("src.platform.analysis_service.urllib.request.urlopen", fake_urlopen)
        summary = StockAnalysisService()._build_ai_summary(
            enabled=True,
            symbol="600519.SH",
            signal={"rating": "watch", "score": 55, "reasons": [], "risks": []},
            indicators={"rsi": 50},
            data_quality={"source": "auto"},
        )
    finally:
        set_config(ConfigManager(config=GlobalConfig()))

    assert summary["status"] == "ok"
    assert summary["model"] == "stock-model"
    assert summary["text"] == "configured summary"


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
    monkeypatch.setattr("src.data_sources.providers.get_provider", lambda source: FakeProvider(_ohlcv_frame(close_offset=0.0)))

    resp = client.post(
        "/api/v2/analysis/run",
        json={"symbol": "600036SH", "source": "auto", "days": 60, "use_ai": True},
    )

    assert resp.status_code == 200
    body = resp.json()
    analysis = body["data"]["analysis"]
    assert analysis["symbol"] == "600036.SH"
    assert analysis["data_quality"]["source"] == "akshare"
    assert analysis["data_quality"]["validation_status"] == "verified"
    assert analysis["ai_summary"]["status"] == "missing_api_key"


def test_chart_data_endpoint_normalizes_short_a_share_symbol(client, monkeypatch):
    monkeypatch.setattr("src.data_sources.providers.get_provider", lambda source: FakeProvider())

    resp = client.get("/api/v2/chart-data?symbol=600036SH&days=20&source=auto")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["symbol"] == "600036.SH"
    assert data["source"] == "akshare"
    assert data["data_quality"]["validation_status"] == "verified"
    assert len(data["dates"]) == 20
    assert len(data["ohlc"]) == 20


def test_local_duckdb_update_list_and_chart_endpoints(client, monkeypatch, tmp_path):
    pytest.importorskip("duckdb")
    from src.core.config import ConfigManager, GlobalConfig, set_config

    monkeypatch.setattr("src.data_sources.providers.get_provider", lambda source: FakeProvider(_ohlcv_frame(30)))
    set_config(ConfigManager(config=GlobalConfig(database={"duckdb_path": str(tmp_path / "market.duckdb")})))
    try:
        update_resp = client.post(
            "/api/v2/local-data/update",
            json={"symbol": "600036SH", "source": "eastmoney", "days": 20},
        )
        assert update_resp.status_code == 200
        update = update_resp.json()["data"]
        assert update["symbol"] == "600036.SH"
        assert update["rows"] == 20

        list_resp = client.get("/api/v2/local-data")
        assert list_resp.status_code == 200
        datasets = list_resp.json()["data"]["datasets"]
        assert datasets[0]["symbol"] == "600036.SH"
        assert datasets[0]["freq"] == "daily"
        assert datasets[0]["rows"] == 20

        chart_resp = client.get("/api/v2/chart-data?symbol=600036SH&days=10&source=local")
        assert chart_resp.status_code == 200
        chart = chart_resp.json()["data"]
        assert chart["symbol"] == "600036.SH"
        assert chart["source"] == "local"
        assert chart["data_quality"]["validation_status"] == "local_duckdb"
        assert len(chart["dates"]) == 10
        assert len(chart["ohlc"]) == 10
    finally:
        set_config(ConfigManager(config=GlobalConfig()))


def test_backtest_endpoint_uses_real_provider_auto_source(client, monkeypatch):
    monkeypatch.setattr(
        "src.data_sources.providers.get_provider",
        lambda source, **kwargs: FakeProvider(_ohlcv_frame(260)),
    )

    resp = client.post(
        "/api/v2/backtest/run",
        json={
            "strategy": "macd",
            "symbols": ["60036"],
            "start": "2024-01-01",
            "end": "2024-12-31",
            "source": "auto",
            "benchmark_source": "auto",
            "engine": "backtrader",
        },
    )

    assert resp.status_code == 200
    metrics = resp.json()["data"]["metrics"]
    assert metrics["strategy"] == "macd"
    assert metrics["_engine"] == "backtrader"
    assert metrics["technical_chart"]["symbol"] == "600036.SH"
    assert "error" not in metrics


def test_analysis_job_endpoint(client, monkeypatch):
    monkeypatch.setattr("src.data_sources.providers.get_provider", lambda source: FakeProvider())

    resp = client.post(
        "/api/v2/analysis/jobs",
        json={"symbol": "600519.SH", "source": "auto", "days": 60},
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
    resp = client.post("/api/v2/analysis/run", json={"symbol": "600519.SH", "source": "sample"})

    assert resp.status_code == 400
