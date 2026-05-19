from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from src.backtest.admission_gates import promote_strategy_gate
from src.platform.api_v2 import create_app


def _promote_admission_gate(strategy_name: str, gate_root: str) -> None:
    promote_strategy_gate(strategy_name, "baseline_registered", params={}, gate_root=gate_root, source="test.baseline")
    promote_strategy_gate(strategy_name, "admission_passed", params={}, gate_root=gate_root, source="test.admission")


def test_api_v2_accounts_transfer_and_allocation_preview(tmp_path):
    app = create_app(enable_cors=False)
    gate_root = str(tmp_path / "gates")
    _promote_admission_gate("s1", gate_root)
    _promote_admission_gate("s2", gate_root)

    with TestClient(app) as client:
        account_a = client.post(
            "/api/v2/accounts",
            json={"tenant_id": "tenant-a", "owner_id": "u1", "initial_cash": 1000.0},
        ).json()["data"]["account"]
        account_b = client.post(
            "/api/v2/accounts",
            json={"tenant_id": "tenant-a", "owner_id": "u2", "initial_cash": 500.0},
        ).json()["data"]["account"]

        listed = client.get("/api/v2/accounts?tenant_id=tenant-a")
        assert listed.status_code == 200
        assert len(listed.json()["data"]["accounts"]) == 2

        transfer = client.post(
            "/api/v2/accounts/transfer",
            json={
                "from_account_id": account_a["account_id"],
                "to_account_id": account_b["account_id"],
                "amount": 100.0,
            },
        )
        assert transfer.status_code == 200
        assert transfer.json()["data"]["transfer"]["from_balance"] == pytest.approx(900.0)

        risk = client.get(f"/api/v2/accounts/{account_a['account_id']}/risk")
        assert risk.status_code == 200
        assert risk.json()["data"]["risk"]["risk_level"] == "low"

        allocation = client.post(
            "/api/v2/portfolio/capital-allocation/preview",
            json={
                "tenant_id": "tenant-a",
                "strategy_weights": {"s1": 0.6, "s2": 0.4},
                "gate_root": gate_root,
                "min_cash_buffer_pct": 0.1,
                "max_strategy_weight": 0.7,
            },
        )
        assert allocation.status_code == 200
        payload = allocation.json()["data"]["allocation"]
        assert payload["deployable_cash"] == pytest.approx(1350.0)
        assert set(payload["allocations"]) == {account_a["account_id"], account_b["account_id"]}


def test_api_v2_allocation_preview_requires_accounts(tmp_path):
    app = create_app(enable_cors=False)
    gate_root = str(tmp_path / "gates")
    _promote_admission_gate("s1", gate_root)

    with TestClient(app) as client:
        response = client.post(
            "/api/v2/portfolio/capital-allocation/preview",
            json={"tenant_id": "missing", "strategy_weights": {"s1": 1.0}, "gate_root": gate_root},
        )

    assert response.status_code == 400
    assert "No active accounts" in response.json()["detail"]


def test_api_v2_allocation_preview_blocks_without_admission_gate(tmp_path):
    app = create_app(enable_cors=False)

    with TestClient(app) as client:
        client.post(
            "/api/v2/accounts",
            json={"tenant_id": "tenant-a", "owner_id": "u1", "initial_cash": 1000.0},
        )
        response = client.post(
            "/api/v2/portfolio/capital-allocation/preview",
            json={
                "tenant_id": "tenant-a",
                "strategy_weights": {"s1": 1.0},
                "gate_root": str(tmp_path / "gates"),
            },
        )

    assert response.status_code == 403
    assert "required=admission_passed" in response.json()["detail"]
