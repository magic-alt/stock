"""
Preflight decision seed parameter tests for launch gate workflow.
"""

import argparse
import json
from types import SimpleNamespace

from scripts import start_production as sp


def _build_config():
    return SimpleNamespace(
        strategy=SimpleNamespace(name="macd"),
        backtest=SimpleNamespace(
            initial_cash=100000.0,
            commission=0.0,
            slippage=0.0,
        ),
    )


def _build_args(**kwargs):
    args = argparse.Namespace(
        config=None,
        mode="paper",
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
        preflight_decision_only=True,
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
    )
    for k, v in kwargs.items():
        setattr(args, k, v)
    return args


def test_extract_replay_params_from_decision_payload():
    payload = {
        "release_decision": {
            "decision_state": "review",
            "recommended_replay": {"params": {"fast": 10, "slow": 30}},
        }
    }
    params = sp._extract_replay_params_from_decision(payload)
    assert params == {"fast": 10, "slow": 30}


def test_run_preflight_uses_seed_replay_params(tmp_path, monkeypatch):
    seed_file = tmp_path / "seed_decision.json"
    seed_file.write_text(
        json.dumps(
            {
                "recommended_replay": {
                    "params": {"fast": 8, "slow": 21},
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    calls = {}
    sp.logger = sp.get_logger("startup")

    def fake_run_preflight_checks(
        *,
        config,
        strategy,
        symbols,
        start,
        end,
        source,
        cache_dir,
        mode,
        cash,
        commission,
        slippage,
        run_backtest_smoke,
        run_paper_smoke,
        alignment_threshold,
        alignment_fail_threshold,
        params,
    ):
        calls["params"] = params
        return {
            "overall": "healthy",
            "summary": {"total": 1, "passed": 1, "warn": 0, "failed": 0, "skipped": 0},
            "analysis": {"advice_level": "info"},
        }

    monkeypatch.setattr(sp, "run_preflight_checks", fake_run_preflight_checks)
    passed, _ = sp._run_preflight_if_requested(
        _build_config(),
        _build_args(
            preflight_decision_seed_file=str(seed_file),
        ),
    )

    assert passed is True
    assert calls["params"] == {"fast": 8, "slow": 21}


def test_run_preflight_cli_params_override_seed(tmp_path, monkeypatch):
    seed_file = tmp_path / "seed_decision.json"
    seed_file.write_text(
        json.dumps({"recommended_replay": {"params": {"fast": 8}}}, ensure_ascii=False),
        encoding="utf-8",
    )
    calls = {}
    sp.logger = sp.get_logger("startup")

    def fake_run_preflight_checks(
        *,
        config,
        strategy,
        symbols,
        start,
        end,
        source,
        cache_dir,
        mode,
        cash,
        commission,
        slippage,
        run_backtest_smoke,
        run_paper_smoke,
        alignment_threshold,
        alignment_fail_threshold,
        params,
    ):
        calls["params"] = params
        return {
            "overall": "healthy",
            "summary": {"total": 1, "passed": 1, "warn": 0, "failed": 0, "skipped": 0},
            "analysis": {"advice_level": "info"},
        }

    monkeypatch.setattr(sp, "run_preflight_checks", fake_run_preflight_checks)
    passed, _ = sp._run_preflight_if_requested(
        _build_config(),
        _build_args(
            preflight_params='{"fast": 13, "slow": 34}',
            preflight_decision_seed_file=str(seed_file),
        ),
    )

    assert passed is True
    assert calls["params"] == {"fast": 13, "slow": 34}


def test_run_preflight_auto_regression_uses_seed_in_next_round(tmp_path, monkeypatch):
    seed_file = tmp_path / "seed_decision.json"
    decision_file = tmp_path / "decision.json"
    calls = []

    def fake_run_preflight_if_requested(config, args):
        calls.append(args.preflight_params)
        if len(calls) == 1:
            return True, {
                "decision_state": "review",
                "decision_reasons": [],
                "required_overrides": [],
                "recommended_replay": {
                    "params": {"fast": 8, "slow": 21},
                },
                "next_actions": [],
                "summary": {},
            }
        return True, {
            "decision_state": "approve",
            "decision_reasons": [],
            "required_overrides": [],
            "recommended_replay": None,
            "next_actions": [],
            "summary": {},
        }

    monkeypatch.setattr(sp, "_run_preflight_if_requested", fake_run_preflight_if_requested)
    config = _build_config()
    args = _build_args(
        preflight_decision_seed_file=str(seed_file),
        preflight_decision_file=str(decision_file),
        preflight_auto_regression=True,
        preflight_auto_rounds=2,
    )

    passed, decision, rounds = sp._run_preflight_decision_only_cycles(config, args)
    assert passed is True
    assert rounds == 2
    assert decision.get("decision_state") == "approve"
    assert len(calls) == 2
    assert calls[0] is None
    assert calls[1] is None


def test_run_preflight_auto_regression_stops_when_missing_replay(tmp_path, monkeypatch):
    seed_file = tmp_path / "seed_decision.json"
    decision_file = tmp_path / "decision.json"
    calls = []

    def fake_run_preflight_if_requested(config, args):
        calls.append(args.preflight_params)
        return True, {
            "decision_state": "review",
            "decision_reasons": [],
            "required_overrides": [],
            "recommended_replay": None,
            "next_actions": [],
            "summary": {},
        }

    monkeypatch.setattr(sp, "_run_preflight_if_requested", fake_run_preflight_if_requested)
    config = _build_config()
    args = _build_args(
        preflight_decision_seed_file=str(seed_file),
        preflight_decision_file=str(decision_file),
        preflight_auto_regression=True,
        preflight_auto_rounds=3,
    )

    passed, decision, rounds = sp._run_preflight_decision_only_cycles(config, args)
    assert passed is True
    assert rounds == 1
    assert decision.get("decision_state") == "review"
    assert len(calls) == 1
