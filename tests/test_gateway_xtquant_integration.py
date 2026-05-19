"""Integration smoke for the XtQuant/QMT gateway using a real SDK environment."""
from __future__ import annotations

import os
from queue import Queue

import pytest


def _env(name: str, *, required: bool = True, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    if required and not value:
        pytest.skip(f"XtQuant integration smoke requires environment variable: {name}")
    return value


@pytest.mark.integration
def test_xtquant_gateway_sdk_integration_smoke():
    account_id = _env("XTQUANT_SMOKE_ACCOUNT")
    from src.gateways.xtquant_gateway import GatewayConfig, XtQuantGateway

    config = GatewayConfig(
        account_id=account_id,
        broker="xtquant",
        terminal_type=_env("XTQUANT_SMOKE_TERMINAL_TYPE", required=False, default="QMT") or "QMT",
        terminal_path=_env("XTQUANT_SMOKE_TERMINAL_PATH", required=False),
        sdk_path=_env("XTQUANT_SMOKE_SDK_PATH", required=False),
        sdk_log_path=_env("XTQUANT_SMOKE_LOG_PATH", required=False),
    )
    gateway = XtQuantGateway(config, Queue())

    assert not gateway.is_stub_mode, gateway.sdk_import_error or "XtQuant gateway unexpectedly fell back to stub mode"

    try:
        result = gateway.run_smoke_test(
            allow_order_submission=os.getenv("ALLOW_LIVE_SMOKE_ORDER") == "1",
        )
    finally:
        gateway.disconnect()

    assert result["sdk_available"] is True
    assert result["stub_mode"] is False
    assert result["connected"] is True, result
    assert result["account_ok"] is True, result
    assert result["positions_ok"] is True, result