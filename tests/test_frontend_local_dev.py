from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_frontend_dev_defaults_use_loopback_api_port():
    client_source = (ROOT / "frontend/src/api/client.ts").read_text(encoding="utf-8")
    vite_config = (ROOT / "frontend/vite.config.ts").read_text(encoding="utf-8")

    assert "http://127.0.0.1:8001" in client_source
    assert "http://127.0.0.1:8001" in vite_config
    assert "VITE_API_BASE_URL" in client_source
    assert "VITE_API_BASE_URL" in vite_config


def test_frontend_auto_connects_paper_gateway_and_uses_explicit_menu_routing():
    app_source = (ROOT / "frontend/src/App.vue").read_text(encoding="utf-8")
    trading_store = (ROOT / "frontend/src/stores/trading.ts").read_text(encoding="utf-8")

    assert '@select="handleMenuSelect"' in app_source
    assert "void router.push(path)" in app_source
    assert "ensurePaperGatewayConnected" in app_source
    assert "DEFAULT_PAPER_CONNECT_PAYLOAD" in trading_store
    assert "broker: 'paper'" in trading_store


def test_frontend_uses_real_market_data_sources_by_default():
    dashboard = (ROOT / "frontend/src/views/Dashboard.vue").read_text(encoding="utf-8")
    data_view = (ROOT / "frontend/src/views/DataView.vue").read_text(encoding="utf-8")
    backtest = (ROOT / "frontend/src/views/Backtest.vue").read_text(encoding="utf-8")

    assert 'value="sample"' not in dashboard
    assert "source: 'auto'" in dashboard
    assert "source: 'local'" in data_view
    assert "source: 'auto'" in backtest
    assert 'value="auto"' in data_view
    assert 'value="akshare"' in dashboard
    assert 'value="sina"' in dashboard
    assert 'value="tencent"' in dashboard
    assert 'value="eastmoney"' in dashboard


def test_data_view_supports_local_duckdb_kline_and_update_controls():
    data_view = (ROOT / "frontend/src/views/DataView.vue").read_text(encoding="utf-8")

    assert "Local DuckDB" in data_view
    assert "/api/v2/local-data" in data_view
    assert "/api/v2/local-data/update" in data_view
    assert "source=local" not in data_view
    assert "echarts.init" in data_view
    assert "type: 'candlestick'" in data_view
    assert "Update Local" in data_view
    assert "selectedDatasetKey" in data_view
