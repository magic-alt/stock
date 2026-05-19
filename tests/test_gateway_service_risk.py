from __future__ import annotations

import pytest

from src.platform.api_server import GatewayService


def test_gateway_service_attaches_risk_manager_and_rejects_before_submit():
    service = GatewayService()
    status = service.connect(
        {
            "mode": "paper",
            "broker": "paper",
            "initial_cash": 100_000.0,
            "enable_risk_check": True,
            "risk_config": {"max_order_value": 10.0},
        }
    )

    assert status["connected"] is True
    assert status["risk_check_enabled"] is True
    assert status["risk_manager_attached"] is True

    with pytest.raises(PermissionError, match="Risk check failed"):
        service.submit_order(
            {
                "symbol": "600519.SH",
                "side": "buy",
                "quantity": 100.0,
                "price": 1.0,
                "order_type": "limit",
            }
        )

    assert service.orders() == []


def test_gateway_service_can_disable_risk_manager():
    service = GatewayService()
    status = service.connect(
        {
            "mode": "paper",
            "broker": "paper",
            "initial_cash": 100_000.0,
            "enable_risk_check": False,
            "risk_config": {"max_order_value": 10.0},
        }
    )

    assert status["connected"] is True
    assert status["risk_check_enabled"] is False
    assert status["risk_manager_attached"] is False

    order = service.submit_order(
        {
            "symbol": "600519.SH",
            "side": "buy",
            "quantity": 100.0,
            "price": 1.0,
            "order_type": "limit",
        }
    )

    assert order["order_id"]
