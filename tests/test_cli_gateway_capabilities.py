"""CLI and gateway capability checks for documented V3.3 features."""
from __future__ import annotations

import json
import subprocess
import sys
from queue import Queue


def test_features_command_outputs_clean_json():
    result = subprocess.run(
        [sys.executable, "unified_backtest_framework.py", "features", "--json"],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert {"backtrader", "zipline"}.issubset(set(payload["backtest_engines"]))
    assert {"xtquant", "qmt", "miniqmt", "xtp", "hundsun", "uft"}.issubset(
        set(payload["live_gateways"])
    )
    assert "eastmoney" in payload["trading_brokers"]
    assert "xtp_sdk_unavailable" not in result.stdout + result.stderr
    assert "uft_sdk_unavailable" not in result.stdout + result.stderr


def test_trading_gateway_import_does_not_probe_broker_sdks():
    result = subprocess.run(
        [sys.executable, "-c", "import src.core.trading_gateway; print('ok')"],
        check=True,
        capture_output=True,
        text=True,
    )

    output = result.stdout + result.stderr
    assert "ok" in output
    assert "xtp_sdk_unavailable" not in output
    assert "uft_sdk_unavailable" not in output


def test_readme_live_gateway_table_matches_feature_summary():
    from unified_backtest_framework import _build_feature_summary

    summary = _build_feature_summary()
    live_gateways = set(summary["live_gateways"])
    trading_brokers = set(summary["trading_brokers"])

    assert {"xtquant", "qmt", "miniqmt"}.issubset(live_gateways)
    assert "xtp" in live_gateways
    assert {"hundsun", "uft"}.issubset(live_gateways)
    assert "eastmoney" in trading_brokers


def test_xtquant_qmt_factory_supports_sdkless_stub_smoke():
    from src.gateways import GatewayConfig, create_gateway

    gateway = create_gateway(
        "qmt",
        GatewayConfig(account_id="TEST_QMT", broker="xtquant", auto_reconnect=False),
        Queue(),
    )

    assert gateway.__class__.__name__ == "XtQuantGateway"
    if gateway.is_stub_mode:
        result = gateway.run_smoke_test(symbol="600519.SH", quantity=100, settle_delay=0.01)
        assert result["connected"] is True
        assert result["stub_mode"] is True
        assert result["sdk_available"] is False
        assert result["account_ok"] is True
        assert result["positions_ok"] is True
        assert result["order_path_executed"] is True
        assert result["order_ok"] is True
        assert result["cancel_ok"] is True
        gateway.disconnect()
    else:
        assert gateway.sdk_available is True


def test_xtp_and_hundsun_factories_support_sdkless_stub_smoke():
    from src.gateways import GatewayConfig, create_gateway

    for broker in ("xtp", "hundsun", "uft"):
        gateway = create_gateway(
            broker,
            GatewayConfig(account_id=f"TEST_{broker.upper()}", broker=broker, auto_reconnect=False),
            Queue(),
        )
        if gateway.is_stub_mode:
            result = gateway.run_smoke_test(symbol="600519.SH", quantity=100, settle_delay=0.01)
            assert result["connected"] is True
            assert result["stub_mode"] is True
            assert result["account_ok"] is True
            assert result["positions_ok"] is True
            assert result["order_path_executed"] is True
            assert result["order_ok"] is True
            gateway.disconnect()
        else:
            assert gateway.sdk_available is True


def test_eastmoney_adapter_is_registered_without_client_login():
    from src.core.trading_gateway import BrokerType, TradingGateway

    gateway = TradingGateway.create_live(BrokerType.EASTMONEY, account="TEST_EASTMONEY")

    assert gateway.config.broker == BrokerType.EASTMONEY
    assert gateway._adapter.__class__.__name__ == "EastMoneyAdapter"