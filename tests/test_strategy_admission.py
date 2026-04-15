"""Tests for historical baseline generation and strategy admission reporting."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd
import yaml

from src.backtest.admission import (
    DEFAULT_STRATEGY_BASELINE_ROOT,
    HistoricalSampleCase,
    compute_params_signature,
    evaluate_admission,
    generate_historical_baseline,
    get_strategy_family,
    load_sample_cases,
    register_strategy_baseline,
    resolve_baseline_snapshot,
    resolve_admission_profile,
    resolve_registered_baseline_artifacts,
    write_admission_artifacts,
    write_baseline_artifacts,
)


def _quality_report(symbols: Sequence[str], *, avg_missing_ratio: float = 0.0) -> Dict[str, Any]:
    return {
        "summary": {"avg_missing_ratio": avg_missing_ratio},
        "per_symbol": {
            symbol: {
                "missing_ratio": avg_missing_ratio,
                "duplicate_rows": 0,
                "nan_rows": 0,
                "ohlc_anomalies": 0,
            }
            for symbol in symbols
        },
    }


def _fail_on_non_finite(token: str) -> None:
    raise ValueError(f"non-finite token in JSON: {token}")


def _run_result(
    symbols: Sequence[str],
    *,
    cum_return: float = 0.18,
    sharpe: float = 0.95,
    mdd: float = 0.12,
    calmar: float = 0.45,
    trades: float = 12.0,
    profit_factor: float = 1.35,
    win_rate: float = 0.52,
    expectancy: float = 0.03,
    avg_missing_ratio: float = 0.0,
) -> Dict[str, Any]:
    nav = pd.Series(
        [1.0, 1.02, 1.05, 1.08, 1.12, 1.18],
        index=pd.bdate_range("2024-01-02", periods=6),
    )
    return {
        "cum_return": cum_return,
        "ann_return": 0.22,
        "ann_vol": 0.16,
        "sharpe": sharpe,
        "mdd": mdd,
        "calmar": calmar,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "expectancy": expectancy,
        "trades": trades,
        "bench_return": 0.08,
        "bench_mdd": 0.10,
        "excess_return": cum_return - 0.08,
        "nav": nav,
        "_quality_report": _quality_report(symbols, avg_missing_ratio=avg_missing_ratio),
        "_data_fingerprint": {"combined": f"fp-{'-'.join(symbols)}"},
    }


class FakeRunner:
    """Minimal runner stub for admission tests."""

    def __init__(self, responses: Dict[Tuple[str, ...], Dict[str, Any]]) -> None:
        self.responses = responses
        self.calls: List[Dict[str, Any]] = []

    def run_strategy(
        self,
        strategy: str,
        symbols: Sequence[str],
        start: str,
        end: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        cash: float = 100000,
        commission: float = 0.001,
        slippage: float = 0.001,
        benchmark: Optional[str] = None,
        adj: Optional[str] = None,
        out_dir: Optional[str] = None,
        enable_plot: bool = False,
        fee_plugin: Optional[str] = None,
        fee_plugin_params: Optional[Dict[str, Any]] = None,
        calendar_mode: Optional[str] = None,
        collect_diagnostics: bool = False,
    ) -> Dict[str, Any]:
        key = tuple(symbols)
        self.calls.append(
            {
                "strategy": strategy,
                "symbols": list(symbols),
                "start": start,
                "end": end,
                "params": params or {},
                "cash": cash,
                "commission": commission,
                "slippage": slippage,
                "benchmark": benchmark,
                "adj": adj,
                "calendar_mode": calendar_mode,
                "collect_diagnostics": collect_diagnostics,
            }
        )
        payload = self.responses.get(key)
        if payload is None:
            raise KeyError(f"Missing fake response for {key}")
        return dict(payload)


def test_load_sample_cases_from_yaml_round_trip(tmp_path: Path) -> None:
    """Sample case files should round-trip through YAML."""
    sample_path = tmp_path / "samples.yaml"
    payload = [
        HistoricalSampleCase(
            sample_id="cn_single_quality_2024",
            description="single window",
            symbols=("600519.SH",),
            start="2024-01-02",
            end="2024-12-31",
            tags=("single", "real-history"),
        ).to_dict(),
        HistoricalSampleCase(
            sample_id="cn_multi_leaders_2024_2025",
            description="multi window",
            symbols=("600519.SH", "000858.SZ"),
            start="2024-01-02",
            end="2025-10-20",
            tags=("multi", "real-history"),
        ).to_dict(),
    ]
    sample_path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")

    loaded = load_sample_cases(str(sample_path))

    assert [case.sample_id for case in loaded] == [
        "cn_single_quality_2024",
        "cn_multi_leaders_2024_2025",
    ]
    assert loaded[0].symbols == ("600519.SH",)
    assert loaded[1].tags == ("multi", "real-history")


def test_generate_historical_baseline_filters_samples_by_strategy_shape() -> None:
    """Single-symbol and multi-symbol strategies should use matching sample windows by default."""
    sample_cases = [
        HistoricalSampleCase(
            sample_id="single_case",
            description="single case",
            symbols=("600519.SH",),
            start="2024-01-02",
            end="2024-12-31",
            tags=("single", "real-history"),
        ),
        HistoricalSampleCase(
            sample_id="multi_case",
            description="multi case",
            symbols=("600519.SH", "000858.SZ"),
            start="2024-01-02",
            end="2025-10-20",
            tags=("multi", "real-history"),
        ),
    ]
    runner = FakeRunner(
        {
            ("600519.SH",): _run_result(("600519.SH",)),
            ("600519.SH", "000858.SZ"): _run_result(("600519.SH", "000858.SZ")),
        }
    )

    single_snapshot = generate_historical_baseline(
        "macd",
        sample_cases=sample_cases,
        runner=runner,
        cache_dir="./cache",
    )
    multi_snapshot = generate_historical_baseline(
        "turning_point",
        sample_cases=sample_cases,
        runner=runner,
        cache_dir="./cache",
    )

    assert [sample["sample"]["sample_id"] for sample in single_snapshot["samples"]] == ["single_case"]
    assert [sample["sample"]["sample_id"] for sample in multi_snapshot["samples"]] == ["multi_case"]


def test_generate_historical_baseline_can_filter_by_regime() -> None:
    """Regime filters should select only matching sample windows."""
    sample_cases = [
        HistoricalSampleCase(
            sample_id="bull_case",
            description="bull case",
            symbols=("600519.SH",),
            start="2024-09-24",
            end="2025-03-31",
            tags=("single", "real-history", "bull"),
        ),
        HistoricalSampleCase(
            sample_id="bear_case",
            description="bear case",
            symbols=("600519.SH",),
            start="2024-01-02",
            end="2024-02-29",
            tags=("single", "real-history", "bear"),
        ),
    ]
    runner = FakeRunner({("600519.SH",): _run_result(("600519.SH",))})

    snapshot = generate_historical_baseline(
        "macd",
        sample_cases=sample_cases,
        regimes=["bear"],
        runner=runner,
    )

    assert [sample["sample"]["sample_id"] for sample in snapshot["samples"]] == ["bear_case"]
    assert snapshot["coverage"]["covered_regimes"] == ["bear"]


def test_resolve_admission_profile_uses_strategy_family_specific_thresholds() -> None:
    """Different strategy families should resolve to different admission thresholds."""
    macd_family, macd_profile = resolve_admission_profile("macd", "institutional")
    boll_family, boll_profile = resolve_admission_profile("bollinger", "institutional")

    assert get_strategy_family("turning_point") == "portfolio"
    assert macd_family == "trend"
    assert boll_family == "mean_reversion"
    assert macd_profile.min_win_rate < boll_profile.min_win_rate
    assert macd_profile.max_mdd > boll_profile.max_mdd


def test_register_and_resolve_single_strategy_baseline(tmp_path: Path) -> None:
    """Registered baselines should be discoverable by strategy without passing a file path."""
    sample_cases = [
        HistoricalSampleCase(
            sample_id="single_case",
            description="single case",
            symbols=("600519.SH",),
            start="2024-01-02",
            end="2024-12-31",
            tags=("single", "real-history", "bull"),
        )
    ]
    runner = FakeRunner({("600519.SH",): _run_result(("600519.SH",))})
    snapshot = generate_historical_baseline("macd", sample_cases=sample_cases, runner=runner, params={"fast": 12})

    artifacts = register_strategy_baseline(snapshot, baseline_root=str(tmp_path), alias="prod")
    resolved_artifacts = resolve_registered_baseline_artifacts("macd", baseline_root=str(tmp_path), alias="prod")
    resolved_snapshot, baseline_context = resolve_baseline_snapshot(
        "macd",
        baseline_root=str(tmp_path),
        alias="prod",
    )

    assert DEFAULT_STRATEGY_BASELINE_ROOT.endswith("strategy_baselines")
    assert Path(artifacts["json"]).exists()
    assert Path(artifacts["registry"]).exists()
    assert resolved_artifacts is not None
    assert resolved_artifacts["json"] == artifacts["json"]
    assert resolved_snapshot is not None
    assert resolved_snapshot["params_signature"] == compute_params_signature({"fast": 12})
    assert baseline_context["mode"] == "strategy_registry"
    assert baseline_context["alias"] == "prod"


def test_evaluate_admission_marks_registered_baseline_param_mismatch() -> None:
    """Regression drift checks should be skipped when the registered baseline uses different params."""
    sample_cases = [
        HistoricalSampleCase(
            sample_id="single_case",
            description="single case",
            symbols=("600519.SH",),
            start="2024-01-02",
            end="2024-12-31",
            tags=("single", "real-history"),
        )
    ]
    baseline_runner = FakeRunner({("600519.SH",): _run_result(("600519.SH",), trades=20.0)})
    current_runner = FakeRunner({("600519.SH",): _run_result(("600519.SH",), trades=18.0)})

    baseline_snapshot = generate_historical_baseline(
        "macd",
        sample_cases=sample_cases,
        runner=baseline_runner,
        params={"fast": 10},
    )
    current_snapshot = generate_historical_baseline(
        "macd",
        sample_cases=sample_cases,
        runner=current_runner,
        params={"fast": 12},
    )
    report = evaluate_admission(
        current_snapshot,
        profile_name="institutional",
        baseline_snapshot=baseline_snapshot,
        baseline_context={
            "mode": "strategy_registry",
            "path": "report/strategy_baselines/macd/prod/historical_baseline.json",
            "alias": "prod",
        },
    )

    assert report["baseline"]["params_match"] is False
    assert report["baseline"]["usable_for_regression"] is False
    assert report["samples"][0]["regression_checks"] == {}


def test_evaluate_admission_returns_watch_for_warning_regression() -> None:
    """Warning-level baseline drift should downgrade admission to WATCH without failing it."""
    sample_cases = [
        HistoricalSampleCase(
            sample_id="single_case",
            description="single case",
            symbols=("600519.SH",),
            start="2024-01-02",
            end="2024-12-31",
            tags=("single", "real-history"),
        )
    ]
    baseline_runner = FakeRunner({("600519.SH",): _run_result(("600519.SH",), trades=20.0)})
    current_runner = FakeRunner({("600519.SH",): _run_result(("600519.SH",), trades=8.0)})

    baseline_snapshot = generate_historical_baseline("macd", sample_cases=sample_cases, runner=baseline_runner)
    current_snapshot = generate_historical_baseline("macd", sample_cases=sample_cases, runner=current_runner)
    report = evaluate_admission(
        current_snapshot,
        profile_name="institutional",
        baseline_snapshot=baseline_snapshot,
    )

    assert report["overall_status"] == "WATCH"
    sample_report = report["samples"][0]
    assert sample_report["status"] == "WATCH"
    assert sample_report["regression_checks"]["trades"]["status"] == "watch"


def test_evaluate_admission_returns_fail_for_threshold_breach() -> None:
    """Required gate breaches should fail admission immediately."""
    sample_cases = [
        HistoricalSampleCase(
            sample_id="single_case",
            description="single case",
            symbols=("600519.SH",),
            start="2024-01-02",
            end="2024-12-31",
            tags=("single", "real-history"),
        )
    ]
    runner = FakeRunner(
        {
            ("600519.SH",): _run_result(
                ("600519.SH",),
                sharpe=0.10,
                mdd=0.38,
                trades=10.0,
            )
        }
    )

    snapshot = generate_historical_baseline("macd", sample_cases=sample_cases, runner=runner)
    report = evaluate_admission(snapshot, profile_name="standard")

    assert report["overall_status"] == "FAIL"
    assert report["samples"][0]["status"] == "FAIL"


def test_artifact_writers_emit_markdown_templates(tmp_path: Path) -> None:
    """Baseline and admission reports should be persisted as JSON + Markdown artifacts."""
    sample_cases = [
        HistoricalSampleCase(
            sample_id="single_case",
            description="single case",
            symbols=("600519.SH",),
            start="2024-01-02",
            end="2024-12-31",
            tags=("single", "real-history"),
        )
    ]
    runner = FakeRunner({("600519.SH",): _run_result(("600519.SH",), profit_factor=float("nan"))})

    snapshot = generate_historical_baseline("macd", sample_cases=sample_cases, runner=runner)
    report = evaluate_admission(snapshot, profile_name="standard")
    baseline_artifacts = write_baseline_artifacts(str(tmp_path), snapshot, prefix="baseline_snapshot")
    admission_artifacts = write_admission_artifacts(str(tmp_path), report)
    baseline_json = Path(baseline_artifacts["json"]).read_text(encoding="utf-8")
    admission_json = Path(admission_artifacts["json"]).read_text(encoding="utf-8")
    baseline_payload = json.loads(baseline_json, parse_constant=_fail_on_non_finite)
    admission_payload = json.loads(admission_json, parse_constant=_fail_on_non_finite)

    assert Path(baseline_artifacts["json"]).exists()
    assert Path(admission_artifacts["json"]).exists()
    assert "# 历史样本回归基线" in Path(baseline_artifacts["markdown"]).read_text(encoding="utf-8")
    assert "# 策略准入报告" in Path(admission_artifacts["markdown"]).read_text(encoding="utf-8")
    assert baseline_payload["samples"][0]["run"]["metrics"]["profit_factor"] is None
    assert admission_payload["samples"][0]["metrics"]["profit_factor"] is None
    assert admission_payload["strategy_family"] == "trend"
    assert admission_payload["baseline"]["mode"] == "missing"
    assert "Regime 覆盖" in Path(admission_artifacts["markdown"]).read_text(encoding="utf-8")
    assert "基线来源" in Path(admission_artifacts["markdown"]).read_text(encoding="utf-8")
