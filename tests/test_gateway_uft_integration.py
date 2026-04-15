"""Integration smoke for the Hundsun UFT gateway using a real SDK environment."""
from __future__ import annotations

import os
from queue import Queue

import pytest


def _env(name: str, *, required: bool = True, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    if required and not value:
        pytest.skip(f"UFT integration smoke requires environment variable: {name}")
    return value


@pytest.mark.integration
def test_uft_gateway_sdk_integration_smoke():
    account_id = _env("UFT_SMOKE_ACCOUNT")
    password = _env("UFT_SMOKE_PASSWORD")
    td_front = _env("UFT_SMOKE_TD_FRONT")
    from src.gateways.hundsun_uft_gateway import GatewayConfig, HundsunUftGateway

    config = GatewayConfig(
        account_id=account_id,
        broker="hundsun",
        password=password,
        td_front=td_front,
        md_front=_env("UFT_SMOKE_MD_FRONT", required=False),
        sdk_path=_env("UFT_SMOKE_SDK_PATH", required=False),
        sdk_log_path=_env("UFT_SMOKE_LOG_PATH", required=False),
    )
    gateway = HundsunUftGateway(config, Queue())

    assert not gateway.is_stub_mode, gateway.sdk_import_error or "UFT gateway unexpectedly fell back to stub mode"

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
