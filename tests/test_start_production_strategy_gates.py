from __future__ import annotations

import argparse
from types import SimpleNamespace

import pytest

from scripts import start_production as sp
from src.backtest.admission_gates import MissingStrategyGateStage, promote_strategy_gate


def _build_config(params=None):
    return SimpleNamespace(
        strategy=SimpleNamespace(name="macd", params=params or {"fast": 12, "slow": 26, "signal": 9}),
        backtest=SimpleNamespace(
            initial_cash=100000.0,
            commission=0.0,
            slippage=0.0,
        ),
    )


def _build_args(**kwargs):
    args = argparse.Namespace(
        config=None,
        mode="live",
        skip_health_check=False,
        preflight=True,
        preflight_mode=None,
        preflight_strategy=None,
        preflight_symbols=["600519.SH"],
        preflight_start=None,
        preflight_end=None,
        preflight_source=None,
        preflight_cache_dir=None,
        preflight_params=None,
        preflight_skip_backtest=False,
        preflight_skip_paper=False,
        preflight_decision_only=False,
        preflight_fail_on_review=False,
        preflight_decision_file=None,
        preflight_allow_warn=False,
        preflight_allow_block=False,
        preflight_platform_run=False,
        preflight_platform_dir="report/preflight_platform",
        preflight_platform_limit=5,
        preflight_sweep=False,
        preflight_sweep_limit=3,
        preflight_use_best=False,
        preflight_auto_regression=False,
        preflight_auto_rounds=1,
        preflight_export=None,
        preflight_alignment_threshold=0.03,
        preflight_alignment_fail_threshold=0.10,
        preflight_json=False,
        preflight_decision_seed_file=None,
        preflight_gate_root=None,
    )
    for key, value in kwargs.items():
        setattr(args, key, value)
    return args


def test_live_preflight_blocks_without_admission_gate(tmp_path, monkeypatch):
    config = _build_config()
    args = _build_args(preflight_gate_root=str(tmp_path / "gates"))
    sp.logger = sp.get_logger("startup")

    def fail_if_called(**kwargs):
        raise AssertionError("run_preflight_checks should not run before gate prerequisite passes")

    monkeypatch.setattr(sp, "run_preflight_checks", fail_if_called)
    passed, decision = sp._run_preflight_if_requested(config, args)

    assert passed is False
    assert decision["decision_state"] == "block"
    assert decision["strategy_gate"]["required_stage"] == "admission_passed"


def test_paper_preflight_blocks_without_baseline_gate(tmp_path, monkeypatch):
    config = _build_config()
    args = _build_args(mode="paper", preflight_mode="paper", preflight_gate_root=str(tmp_path / "gates"))
    sp.logger = sp.get_logger("startup")

    def fail_if_called(**kwargs):
        raise AssertionError("paper preflight should not run before baseline gate passes")

    monkeypatch.setattr(sp, "run_preflight_checks", fail_if_called)
    passed, decision = sp._run_preflight_if_requested(config, args)

    assert passed is False
    assert decision["decision_state"] == "block"
    assert decision["strategy_gate"]["required_stage"] == "baseline_registered"


def test_paper_preflight_allows_baseline_without_promoting_paper_gate(tmp_path, monkeypatch):
    params = {"fast": 12, "slow": 26, "signal": 9}
    gate_root = str(tmp_path / "gates")
    config = _build_config(params=params)
    args = _build_args(mode="paper", preflight_mode="paper", preflight_gate_root=gate_root)
    sp.logger = sp.get_logger("startup")

    promote_strategy_gate("macd", "baseline_registered", params=params, gate_root=gate_root, source="test.baseline")

    def fake_run_preflight_checks(**kwargs):
        return {
            "overall": "healthy",
            "summary": {"total": 1, "passed": 1, "warn": 0, "failed": 0, "skipped": 0},
            "checks": [
                {"name": "paper_smoke", "status": "pass", "message": "ok", "details": {}},
            ],
            "analysis": {"advice_level": "info", "candidate_grid": [], "candidate_plan": {}},
            "config": {
                "strategy": "macd",
                "requested_strategy": "macd",
                "strategy_params_requested": params,
                "strategy_params_unified_for_replay": params,
                "symbols": ["600519.SH"],
                "source": "akshare",
                "cache_dir": "./cache",
                "mode": "paper",
                "alignment_threshold": 0.03,
                "alignment_fail_threshold": 0.10,
                "alias_resolved": False,
            },
            "backtest": {},
            "paper": {},
        }

    monkeypatch.setattr(sp, "run_preflight_checks", fake_run_preflight_checks)
    passed, decision = sp._run_preflight_if_requested(config, args)

    assert passed is True
    assert decision["strategy_gate"]["current_stage"] == "baseline_registered"
    sp._require_paper_launch_gate(config, args)


def test_live_preflight_promotes_live_candidate_and_production(tmp_path, monkeypatch):
    params = {"fast": 12, "slow": 26, "signal": 9}
    gate_root = str(tmp_path / "gates")
    config = _build_config(params=params)
    args = _build_args(preflight_gate_root=gate_root)
    sp.logger = sp.get_logger("startup")

    promote_strategy_gate("macd", "baseline_registered", params=params, gate_root=gate_root, source="test.baseline")
    promote_strategy_gate("macd", "admission_passed", params=params, gate_root=gate_root, source="test.admission")

    def fake_run_preflight_checks(**kwargs):
        return {
            "overall": "healthy",
            "summary": {"total": 2, "passed": 2, "warn": 0, "failed": 0, "skipped": 0},
            "checks": [
                {"name": "backtest_smoke", "status": "pass", "message": "ok", "details": {}},
                {"name": "paper_smoke", "status": "pass", "message": "ok", "details": {}},
            ],
            "analysis": {"advice_level": "info", "candidate_grid": [], "candidate_plan": {}},
            "config": {
                "strategy": "macd",
                "requested_strategy": "macd",
                "strategy_params_requested": params,
                "strategy_params_unified_for_replay": params,
                "symbols": ["600519.SH"],
                "source": "akshare",
                "cache_dir": "./cache",
                "mode": "live",
                "alignment_threshold": 0.03,
                "alignment_fail_threshold": 0.10,
                "alias_resolved": False,
            },
            "backtest": {},
            "paper": {},
        }

    monkeypatch.setattr(sp, "run_preflight_checks", fake_run_preflight_checks)
    passed, decision = sp._run_preflight_if_requested(config, args)

    assert passed is True
    assert decision["strategy_gate"]["current_stage"] == "live_candidate"
    sp._require_live_launch_gate(config, args)
    production_gate = sp._mark_live_production_gate(config, args)
    assert production_gate["current_stage"] == "production"


def test_live_launch_requires_live_candidate_stage(tmp_path):
    config = _build_config()
    args = _build_args(preflight_gate_root=str(tmp_path / "gates"), preflight=False)

    with pytest.raises(MissingStrategyGateStage):
        sp._require_live_launch_gate(config, args)


def test_paper_launch_requires_baseline_stage(tmp_path):
    config = _build_config()
    args = _build_args(mode="paper", preflight_gate_root=str(tmp_path / "gates"), preflight=False)

    with pytest.raises(MissingStrategyGateStage):
        sp._require_paper_launch_gate(config, args)