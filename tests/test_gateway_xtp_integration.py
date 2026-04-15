"""Integration smoke for the XTP gateway using a real SDK environment."""
from __future__ import annotations

import os
from queue import Queue

import pytest


def _env(name: str, *, required: bool = True, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    if required and not value:
        pytest.skip(f"XTP integration smoke requires environment variable: {name}")
    return value


@pytest.mark.integration
def test_xtp_gateway_sdk_integration_smoke():
    account_id = _env("XTP_SMOKE_ACCOUNT")
    password = _env("XTP_SMOKE_PASSWORD")
    trade_server = _env("XTP_SMOKE_TRADE_SERVER")
    quote_server = _env("XTP_SMOKE_QUOTE_SERVER")
    from src.gateways.xtp_gateway import GatewayConfig, XtpGateway

    config = GatewayConfig(
        account_id=account_id,
        broker="xtp",
        password=password,
        trade_server=trade_server,
        quote_server=quote_server,
        client_id=int(_env("XTP_SMOKE_CLIENT_ID", default="1") or "1"),
        sdk_path=_env("XTP_SMOKE_SDK_PATH", required=False),
        sdk_log_path=_env("XTP_SMOKE_LOG_PATH", required=False),
    )
    gateway = XtpGateway(config, Queue())

    assert not gateway.is_stub_mode, gateway.sdk_import_error or "XTP gateway unexpectedly fell back to stub mode"

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
