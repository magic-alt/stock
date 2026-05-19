from __future__ import annotations

from queue import Queue


def test_xtquant_smoke_runs_order_path_in_stub_mode():
    from src.gateways.base_live_gateway import GatewayConfig
    from src.gateways.xtquant_gateway import XtQuantGateway

    gateway = XtQuantGateway(
        GatewayConfig(
            account_id="SMOKE_XTQUANT",
            broker="xtquant",
            terminal_type="QMT",
            auto_reconnect=False,
        ),
        Queue(),
    )

    result = gateway.run_smoke_test(price=1800.0)

    assert result["connected"] is True
    assert result["stub_mode"] is True
    assert result["sdk_available"] is False
    assert result["account_ok"] is True
    assert result["positions_ok"] is True
    assert result["order_path_executed"] is True
    assert result["order_ok"] is True
    assert result["final_order_status"] == "cancelled"
    assert gateway.sdk_import_error

    gateway.disconnect()


def test_xtquant_smoke_can_skip_order_submission():
    from src.gateways.base_live_gateway import GatewayConfig
    from src.gateways.xtquant_gateway import XtQuantGateway

    gateway = XtQuantGateway(
        GatewayConfig(
            account_id="SMOKE_XTQUANT_SKIP",
            broker="xtquant",
            terminal_type="QMT",
            auto_reconnect=False,
        ),
        Queue(),
    )

    result = gateway.run_smoke_test(allow_order_submission=False)

    assert result["connected"] is True
    assert result["order_path_executed"] is False
    assert result["account_ok"] is True
    assert result["positions_ok"] is True

    gateway.disconnect()