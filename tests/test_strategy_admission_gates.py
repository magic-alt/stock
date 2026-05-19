from __future__ import annotations

import pytest

from src.backtest.admission_gates import (
    build_strategy_gate_summary,
    load_strategy_gate,
    MissingStrategyGateStage,
    promote_strategy_gate,
    require_strategy_stage,
)
from unified_backtest_framework import _parse_params_list_option, _require_admission_gates_for_strategies


def test_strategy_gate_advances_in_order(tmp_path):
    gate_root = str(tmp_path / "gates")
    params = {"fast": 12, "slow": 26, "signal": 9}

    promote_strategy_gate("macd", "research", params=params, gate_root=gate_root, source="test.research")
    promote_strategy_gate("macd", "baseline_registered", params=params, gate_root=gate_root, source="test.baseline")
    promote_strategy_gate("macd", "admission_passed", params=params, gate_root=gate_root, source="test.admission")
    promote_strategy_gate("macd", "paper_validated", params=params, gate_root=gate_root, source="test.paper")
    promote_strategy_gate("macd", "live_candidate", params=params, gate_root=gate_root, source="test.live")
    gate_payload = promote_strategy_gate("macd", "production", params=params, gate_root=gate_root, source="test.production")

    assert gate_payload["current_stage"] == "production"
    assert len(gate_payload["history"]) >= 6
    assert build_strategy_gate_summary(gate_payload)["current_stage_index"] == 5


def test_strategy_gate_reset_requires_revalidation(tmp_path):
    gate_root = str(tmp_path / "gates")
    params = {"fast": 12, "slow": 26, "signal": 9}

    promote_strategy_gate("macd", "baseline_registered", params=params, gate_root=gate_root, source="test.baseline")
    promote_strategy_gate("macd", "admission_passed", params=params, gate_root=gate_root, source="test.admission")
    promote_strategy_gate("macd", "paper_validated", params=params, gate_root=gate_root, source="test.paper")
    gate_payload = promote_strategy_gate(
        "macd",
        "baseline_registered",
        params=params,
        gate_root=gate_root,
        source="test.baseline.refresh",
        allow_reset=True,
        details={"baseline_alias": "prod"},
    )

    assert gate_payload["current_stage"] == "baseline_registered"
    assert gate_payload["history"][-1]["details"]["reset_from_stage"] == "paper_validated"
    require_strategy_stage("macd", "baseline_registered", params=params, gate_root=gate_root)
    loaded = load_strategy_gate("macd", params=params, gate_root=gate_root)
    assert loaded is not None
    assert loaded["results"]["baseline_registered"]["baseline_alias"] == "prod"


def test_combo_params_list_requires_matching_length():
    with pytest.raises(ValueError, match="length must match"):
        _parse_params_list_option(
            '[{"fast": 12}]',
            option_name="--params-list",
            expected_count=2,
        )


def test_combo_requires_admission_passed_for_each_leg(tmp_path):
    gate_root = str(tmp_path / "gates")
    params = {"fast": 12, "slow": 26, "signal": 9}

    promote_strategy_gate("macd", "baseline_registered", params=params, gate_root=gate_root, source="test.baseline")
    with pytest.raises(MissingStrategyGateStage):
        _require_admission_gates_for_strategies(["macd"], [params], gate_root=gate_root)

    promote_strategy_gate("macd", "admission_passed", params=params, gate_root=gate_root, source="test.admission")

    _require_admission_gates_for_strategies(["macd"], [params], gate_root=gate_root)