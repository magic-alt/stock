"""
Historical regression baseline and strategy admission reporting.

This module provides:
- deterministic historical sample definitions
- baseline snapshot generation from real market data
- admission evaluation with quality/performance/regression gates
- markdown/json artifact writers for review workflows
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Protocol, Sequence, Tuple

import pandas as pd
import yaml

from src.backtest.repro import _to_builtin
from src.backtest.strategy_modules import STRATEGY_REGISTRY


TRACKED_METRICS: Tuple[str, ...] = (
    "cum_return",
    "ann_return",
    "ann_vol",
    "sharpe",
    "mdd",
    "calmar",
    "win_rate",
    "profit_factor",
    "expectancy",
    "trades",
    "bench_return",
    "bench_mdd",
    "excess_return",
)

REGIME_TAGS: Tuple[str, ...] = ("bull", "bear", "range", "high-vol")
DEFAULT_STRATEGY_BASELINE_ROOT = os.path.join("report", "strategy_baselines")

STRATEGY_FAMILY_MAP: Dict[str, str] = {
    "ema": "trend",
    "macd": "trend",
    "macd_e": "trend",
    "macd_r": "trend",
    "triple_ma": "trend",
    "adx_trend": "trend",
    "sma_cross": "trend",
    "kama": "trend",
    "macd_zero": "trend",
    "macd_hist": "trend",
    "kama_opt": "trend",
    "trend_pullback_enhanced": "trend",
    "rsi_trend": "trend",
    "triple_ma_adx": "trend",
    "macd_impulse": "trend",
    "sma_trend_following": "trend",
    "bollinger": "mean_reversion",
    "boll_e": "mean_reversion",
    "rsi": "mean_reversion",
    "keltner": "mean_reversion",
    "zscore": "mean_reversion",
    "rsi_ma_filter": "mean_reversion",
    "rsi_divergence": "mean_reversion",
    "auction_open": "mean_reversion",
    "intraday_reversion": "mean_reversion",
    "intraday_opt": "mean_reversion",
    "bollinger_rsi": "mean_reversion",
    "zscore_enhanced": "mean_reversion",
    "keltner_adaptive": "mean_reversion",
    "donchian": "breakout",
    "donchian_atr": "breakout",
    "futures_ma_cross": "futures",
    "futures_grid": "futures",
    "futures_market_making": "futures",
    "turtle_futures": "futures",
    "futures_grid_atr": "futures",
    "multifactor_selection": "portfolio",
    "index_enhancement": "portfolio",
    "industry_rotation": "portfolio",
    "multifactor_robust": "portfolio",
    "turning_point": "portfolio",
    "risk_parity": "portfolio",
    "ml_walk": "machine_learning",
    "ml_meta": "machine_learning",
    "ml_prob_band": "machine_learning",
    "qlib_registry": "machine_learning",
}


class StrategyRunner(Protocol):
    """Protocol for strategy execution used by baseline/admission flows."""

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
        ...


@dataclass(frozen=True)
class HistoricalSampleCase:
    """A real historical sample definition used for regression/admission runs."""

    sample_id: str
    description: str
    symbols: Tuple[str, ...]
    start: str
    end: str
    source: str = "akshare"
    benchmark: Optional[str] = "000300.SH"
    benchmark_source: Optional[str] = None
    adj: Optional[str] = None
    calendar: str = "fill"
    tags: Tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["symbols"] = list(self.symbols)
        payload["tags"] = list(self.tags)
        return payload

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "HistoricalSampleCase":
        return cls(
            sample_id=str(payload["sample_id"]),
            description=str(payload.get("description", payload["sample_id"])),
            symbols=tuple(payload["symbols"]),
            start=str(payload["start"]),
            end=str(payload["end"]),
            source=str(payload.get("source", "akshare")),
            benchmark=payload.get("benchmark"),
            benchmark_source=payload.get("benchmark_source"),
            adj=payload.get("adj"),
            calendar=str(payload.get("calendar", "fill")),
            tags=tuple(payload.get("tags", [])),
        )

    def with_overrides(
        self,
        *,
        source: Optional[str] = None,
        benchmark_source: Optional[str] = None,
        calendar: Optional[str] = None,
        adj: Optional[str] = None,
    ) -> "HistoricalSampleCase":
        return HistoricalSampleCase(
            sample_id=self.sample_id,
            description=self.description,
            symbols=self.symbols,
            start=self.start,
            end=self.end,
            source=source or self.source,
            benchmark=self.benchmark,
            benchmark_source=benchmark_source or self.benchmark_source,
            adj=self.adj if adj is None else adj,
            calendar=calendar or self.calendar,
            tags=self.tags,
        )


@dataclass(frozen=True)
class RegressionTolerance:
    """Allowed drift versus the stored baseline for one metric."""

    absolute: Optional[float] = None
    relative: Optional[float] = None
    severity: str = "warning"  # warning | required


@dataclass(frozen=True)
class AdmissionProfile:
    """Threshold profile for strategy qualification."""

    name: str
    description: str
    min_sharpe: float
    max_mdd: float
    min_calmar: float
    min_trades: int
    min_profit_factor: float
    min_win_rate: float
    min_expectancy: float
    max_avg_missing_ratio: float
    max_symbol_missing_ratio: float
    max_duplicate_rows: int
    max_nan_rows: int
    max_ohlc_anomalies: int
    regression_tolerances: Dict[str, RegressionTolerance]


DEFAULT_HISTORICAL_SAMPLE_CASES: Tuple[HistoricalSampleCase, ...] = (
    HistoricalSampleCase(
        sample_id="cn_single_bear_q1_2024",
        description="A-share single-name bearish drawdown window",
        symbols=("600519.SH",),
        start="2024-01-02",
        end="2024-02-29",
        source="akshare",
        benchmark="000300.SH",
        benchmark_source="akshare",
        calendar="fill",
        tags=("single", "cn", "daily", "real-history", "bear"),
    ),
    HistoricalSampleCase(
        sample_id="cn_single_range_mid_2024",
        description="A-share single-name sideways market window",
        symbols=("600519.SH",),
        start="2024-03-01",
        end="2024-08-30",
        source="akshare",
        benchmark="000300.SH",
        benchmark_source="akshare",
        calendar="fill",
        tags=("single", "cn", "daily", "real-history", "range"),
    ),
    HistoricalSampleCase(
        sample_id="cn_single_high_vol_q4_2024",
        description="A-share single-name policy-driven high-volatility window",
        symbols=("600519.SH",),
        start="2024-09-02",
        end="2024-10-31",
        source="akshare",
        benchmark="000300.SH",
        benchmark_source="akshare",
        calendar="fill",
        tags=("single", "cn", "daily", "real-history", "high-vol"),
    ),
    HistoricalSampleCase(
        sample_id="cn_single_bull_q4_2024",
        description="A-share single-name bullish rebound window",
        symbols=("601318.SH",),
        start="2024-11-01",
        end="2024-12-31",
        source="akshare",
        benchmark="000300.SH",
        benchmark_source="akshare",
        calendar="fill",
        tags=("single", "cn", "daily", "real-history", "bull"),
    ),
    HistoricalSampleCase(
        sample_id="cn_single_quality_2024",
        description="A-share single-name quality baseline window",
        symbols=("600519.SH",),
        start="2024-01-02",
        end="2024-12-31",
        source="akshare",
        benchmark="000300.SH",
        benchmark_source="akshare",
        calendar="fill",
        tags=("single", "cn", "daily", "real-history", "mixed", "broad-window"),
    ),
    HistoricalSampleCase(
        sample_id="cn_single_financial_2024_2025",
        description="A-share single-name recent financial cycle window",
        symbols=("600036.SH",),
        start="2024-01-02",
        end="2025-10-14",
        source="akshare",
        benchmark="000300.SH",
        benchmark_source="akshare",
        calendar="fill",
        tags=("single", "cn", "daily", "real-history", "mixed", "recent", "broad-window"),
    ),
    HistoricalSampleCase(
        sample_id="cn_multi_bear_q1_2024",
        description="A-share multi-asset bearish drawdown basket",
        symbols=("600519.SH", "601318.SH", "600036.SH"),
        start="2024-01-02",
        end="2024-02-29",
        source="akshare",
        benchmark="000300.SH",
        benchmark_source="akshare",
        calendar="fill",
        tags=("multi", "cn", "daily", "real-history", "bear"),
    ),
    HistoricalSampleCase(
        sample_id="cn_multi_range_mid_2024",
        description="A-share multi-asset sideways basket window",
        symbols=("600519.SH", "601318.SH", "600036.SH"),
        start="2024-03-01",
        end="2024-08-30",
        source="akshare",
        benchmark="000300.SH",
        benchmark_source="akshare",
        calendar="fill",
        tags=("multi", "cn", "daily", "real-history", "range"),
    ),
    HistoricalSampleCase(
        sample_id="cn_multi_high_vol_q4_2024",
        description="A-share multi-asset high-volatility basket window",
        symbols=("600519.SH", "601318.SH", "600036.SH"),
        start="2024-09-02",
        end="2024-10-31",
        source="akshare",
        benchmark="000300.SH",
        benchmark_source="akshare",
        calendar="fill",
        tags=("multi", "cn", "daily", "real-history", "high-vol"),
    ),
    HistoricalSampleCase(
        sample_id="cn_multi_bull_q4_2024",
        description="A-share multi-asset bullish rebound basket window",
        symbols=("600519.SH", "601318.SH", "600036.SH"),
        start="2024-11-01",
        end="2024-12-31",
        source="akshare",
        benchmark="000300.SH",
        benchmark_source="akshare",
        calendar="fill",
        tags=("multi", "cn", "daily", "real-history", "bull"),
    ),
    HistoricalSampleCase(
        sample_id="cn_multi_leaders_2024_2025",
        description="A-share multi-asset leadership basket window",
        symbols=("600519.SH", "601318.SH", "600036.SH"),
        start="2024-01-02",
        end="2025-10-14",
        source="akshare",
        benchmark="000300.SH",
        benchmark_source="akshare",
        calendar="fill",
        tags=("multi", "cn", "daily", "real-history", "mixed", "broad-window"),
    ),
)


ADMISSION_PROFILES: Dict[str, AdmissionProfile] = {
    "standard": AdmissionProfile(
        name="standard",
        description="Research admission with basic risk and execution discipline.",
        min_sharpe=0.20,
        max_mdd=0.35,
        min_calmar=0.15,
        min_trades=3,
        min_profit_factor=1.00,
        min_win_rate=0.40,
        min_expectancy=0.0,
        max_avg_missing_ratio=0.05,
        max_symbol_missing_ratio=0.10,
        max_duplicate_rows=0,
        max_nan_rows=0,
        max_ohlc_anomalies=0,
        regression_tolerances={
            "cum_return": RegressionTolerance(absolute=0.08, relative=0.25, severity="required"),
            "sharpe": RegressionTolerance(absolute=0.35, relative=0.35, severity="required"),
            "mdd": RegressionTolerance(absolute=0.06, relative=0.30, severity="required"),
            "trades": RegressionTolerance(absolute=8.0, relative=0.50, severity="warning"),
        },
    ),
    "institutional": AdmissionProfile(
        name="institutional",
        description="Fund-manager style admission with tighter stability and drawdown requirements.",
        min_sharpe=0.35,
        max_mdd=0.25,
        min_calmar=0.25,
        min_trades=5,
        min_profit_factor=1.05,
        min_win_rate=0.45,
        min_expectancy=0.0,
        max_avg_missing_ratio=0.03,
        max_symbol_missing_ratio=0.05,
        max_duplicate_rows=0,
        max_nan_rows=0,
        max_ohlc_anomalies=0,
        regression_tolerances={
            "cum_return": RegressionTolerance(absolute=0.05, relative=0.20, severity="required"),
            "sharpe": RegressionTolerance(absolute=0.25, relative=0.25, severity="required"),
            "mdd": RegressionTolerance(absolute=0.04, relative=0.20, severity="required"),
            "trades": RegressionTolerance(absolute=5.0, relative=0.35, severity="warning"),
            "profit_factor": RegressionTolerance(absolute=0.20, relative=0.20, severity="warning"),
        },
    ),
}


def _merge_regression_tolerances(
    base: Dict[str, RegressionTolerance],
    **updates: RegressionTolerance,
) -> Dict[str, RegressionTolerance]:
    merged = dict(base)
    merged.update(updates)
    return merged


STRATEGY_FAMILY_PROFILES: Dict[str, Dict[str, AdmissionProfile]] = {
    "trend": {
        "standard": replace(
            ADMISSION_PROFILES["standard"],
            name="standard:trend",
            description="Trend-following admission profile with tolerance for lower hit-rate and moderate drawdown.",
            min_sharpe=0.25,
            max_mdd=0.30,
            min_calmar=0.18,
            min_trades=3,
            min_profit_factor=1.02,
            min_win_rate=0.38,
            regression_tolerances=_merge_regression_tolerances(
                ADMISSION_PROFILES["standard"].regression_tolerances,
                cum_return=RegressionTolerance(absolute=0.07, relative=0.25, severity="required"),
                sharpe=RegressionTolerance(absolute=0.30, relative=0.30, severity="required"),
                mdd=RegressionTolerance(absolute=0.05, relative=0.25, severity="required"),
            ),
        ),
        "institutional": replace(
            ADMISSION_PROFILES["institutional"],
            name="institutional:trend",
            description="Fund-manager trend profile emphasizing stability, controlled drawdown, and repeatable momentum capture.",
            min_sharpe=0.40,
            max_mdd=0.24,
            min_calmar=0.30,
            min_trades=5,
            min_profit_factor=1.05,
            min_win_rate=0.40,
            regression_tolerances=_merge_regression_tolerances(
                ADMISSION_PROFILES["institutional"].regression_tolerances,
                cum_return=RegressionTolerance(absolute=0.05, relative=0.18, severity="required"),
                sharpe=RegressionTolerance(absolute=0.22, relative=0.22, severity="required"),
                mdd=RegressionTolerance(absolute=0.04, relative=0.18, severity="required"),
            ),
        ),
    },
    "mean_reversion": {
        "standard": replace(
            ADMISSION_PROFILES["standard"],
            name="standard:mean_reversion",
            description="Mean-reversion research profile expecting tighter drawdown and a better hit-rate.",
            min_sharpe=0.30,
            max_mdd=0.25,
            min_calmar=0.20,
            min_trades=6,
            min_profit_factor=1.08,
            min_win_rate=0.48,
            regression_tolerances=_merge_regression_tolerances(
                ADMISSION_PROFILES["standard"].regression_tolerances,
                mdd=RegressionTolerance(absolute=0.05, relative=0.20, severity="required"),
                trades=RegressionTolerance(absolute=10.0, relative=0.45, severity="warning"),
                profit_factor=RegressionTolerance(absolute=0.15, relative=0.15, severity="warning"),
            ),
        ),
        "institutional": replace(
            ADMISSION_PROFILES["institutional"],
            name="institutional:mean_reversion",
            description="Fund-manager mean-reversion profile with tight drawdown control and higher hit-rate expectations.",
            min_sharpe=0.45,
            max_mdd=0.18,
            min_calmar=0.35,
            min_trades=10,
            min_profit_factor=1.12,
            min_win_rate=0.55,
            regression_tolerances=_merge_regression_tolerances(
                ADMISSION_PROFILES["institutional"].regression_tolerances,
                cum_return=RegressionTolerance(absolute=0.04, relative=0.18, severity="required"),
                sharpe=RegressionTolerance(absolute=0.20, relative=0.20, severity="required"),
                mdd=RegressionTolerance(absolute=0.03, relative=0.15, severity="required"),
                profit_factor=RegressionTolerance(absolute=0.12, relative=0.12, severity="warning"),
            ),
        ),
    },
    "breakout": {
        "standard": replace(
            ADMISSION_PROFILES["standard"],
            name="standard:breakout",
            description="Breakout research profile balancing lower hit-rate with broader upside capture.",
            min_sharpe=0.22,
            max_mdd=0.33,
            min_calmar=0.17,
            min_trades=4,
            min_profit_factor=1.03,
            min_win_rate=0.36,
        ),
        "institutional": replace(
            ADMISSION_PROFILES["institutional"],
            name="institutional:breakout",
            description="Fund-manager breakout profile with tighter drawdown and drift tolerance than generic trend systems.",
            min_sharpe=0.38,
            max_mdd=0.25,
            min_calmar=0.28,
            min_trades=6,
            min_profit_factor=1.05,
            min_win_rate=0.38,
            regression_tolerances=_merge_regression_tolerances(
                ADMISSION_PROFILES["institutional"].regression_tolerances,
                cum_return=RegressionTolerance(absolute=0.05, relative=0.18, severity="required"),
                sharpe=RegressionTolerance(absolute=0.24, relative=0.24, severity="required"),
            ),
        ),
    },
    "portfolio": {
        "standard": replace(
            ADMISSION_PROFILES["standard"],
            name="standard:portfolio",
            description="Portfolio and rotation profile focused on diversified returns and lower drawdown.",
            min_sharpe=0.25,
            max_mdd=0.22,
            min_calmar=0.18,
            min_trades=2,
            min_profit_factor=1.00,
            min_win_rate=0.45,
            regression_tolerances=_merge_regression_tolerances(
                ADMISSION_PROFILES["standard"].regression_tolerances,
                trades=RegressionTolerance(absolute=3.0, relative=0.50, severity="warning"),
                mdd=RegressionTolerance(absolute=0.04, relative=0.20, severity="required"),
            ),
        ),
        "institutional": replace(
            ADMISSION_PROFILES["institutional"],
            name="institutional:portfolio",
            description="Fund-manager portfolio profile with lower drawdown budget and tighter cross-window stability requirements.",
            min_sharpe=0.35,
            max_mdd=0.18,
            min_calmar=0.28,
            min_trades=3,
            min_profit_factor=1.03,
            min_win_rate=0.48,
            regression_tolerances=_merge_regression_tolerances(
                ADMISSION_PROFILES["institutional"].regression_tolerances,
                cum_return=RegressionTolerance(absolute=0.04, relative=0.15, severity="required"),
                sharpe=RegressionTolerance(absolute=0.20, relative=0.20, severity="required"),
                mdd=RegressionTolerance(absolute=0.03, relative=0.15, severity="required"),
                trades=RegressionTolerance(absolute=2.0, relative=0.50, severity="warning"),
            ),
        ),
    },
    "futures": {
        "standard": replace(
            ADMISSION_PROFILES["standard"],
            name="standard:futures",
            description="Futures profile allowing higher turnover and wider drawdown while keeping execution discipline.",
            min_sharpe=0.20,
            max_mdd=0.35,
            min_calmar=0.15,
            min_trades=8,
            min_profit_factor=1.02,
            min_win_rate=0.40,
            regression_tolerances=_merge_regression_tolerances(
                ADMISSION_PROFILES["standard"].regression_tolerances,
                trades=RegressionTolerance(absolute=15.0, relative=0.40, severity="warning"),
            ),
        ),
        "institutional": replace(
            ADMISSION_PROFILES["institutional"],
            name="institutional:futures",
            description="Fund-manager futures profile requiring higher turnover evidence and tighter stability than research mode.",
            min_sharpe=0.35,
            max_mdd=0.26,
            min_calmar=0.25,
            min_trades=12,
            min_profit_factor=1.05,
            min_win_rate=0.42,
            regression_tolerances=_merge_regression_tolerances(
                ADMISSION_PROFILES["institutional"].regression_tolerances,
                trades=RegressionTolerance(absolute=12.0, relative=0.35, severity="warning"),
                mdd=RegressionTolerance(absolute=0.05, relative=0.20, severity="required"),
            ),
        ),
    },
    "machine_learning": {
        "standard": replace(
            ADMISSION_PROFILES["standard"],
            name="standard:machine_learning",
            description="ML profile requiring moderate edge plus tighter regression awareness than rules-based research.",
            min_sharpe=0.25,
            max_mdd=0.30,
            min_calmar=0.18,
            min_trades=4,
            min_profit_factor=1.02,
            min_win_rate=0.42,
            regression_tolerances=_merge_regression_tolerances(
                ADMISSION_PROFILES["standard"].regression_tolerances,
                cum_return=RegressionTolerance(absolute=0.06, relative=0.20, severity="required"),
                sharpe=RegressionTolerance(absolute=0.28, relative=0.25, severity="required"),
            ),
        ),
        "institutional": replace(
            ADMISSION_PROFILES["institutional"],
            name="institutional:machine_learning",
            description="Fund-manager ML profile with tighter drift tolerance and lower drawdown budget.",
            min_sharpe=0.38,
            max_mdd=0.22,
            min_calmar=0.30,
            min_trades=6,
            min_profit_factor=1.05,
            min_win_rate=0.45,
            regression_tolerances=_merge_regression_tolerances(
                ADMISSION_PROFILES["institutional"].regression_tolerances,
                cum_return=RegressionTolerance(absolute=0.04, relative=0.15, severity="required"),
                sharpe=RegressionTolerance(absolute=0.18, relative=0.18, severity="required"),
                mdd=RegressionTolerance(absolute=0.03, relative=0.15, severity="required"),
                trades=RegressionTolerance(absolute=4.0, relative=0.30, severity="warning"),
            ),
        ),
    },
}


def get_strategy_family(strategy_name: str) -> str:
    """Return the configured admission family for a strategy."""
    if strategy_name not in STRATEGY_REGISTRY:
        raise KeyError(f"Unknown strategy: {strategy_name}")
    return STRATEGY_FAMILY_MAP.get(strategy_name, "generic")


def resolve_admission_profile(strategy_name: str, profile_name: str = "institutional") -> Tuple[str, AdmissionProfile]:
    """Resolve a strategy-family-specific admission profile."""
    if profile_name not in ADMISSION_PROFILES:
        raise KeyError(f"Unknown admission profile: {profile_name}")
    family = get_strategy_family(strategy_name)
    profile = STRATEGY_FAMILY_PROFILES.get(family, {}).get(profile_name, ADMISSION_PROFILES[profile_name])
    return family, profile


def compute_params_signature(params: Optional[Dict[str, Any]] = None) -> str:
    """Build a deterministic signature for a strategy parameter set."""
    payload = json.dumps(
        _to_builtin(params or {}),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _normalize_baseline_alias(alias: str) -> str:
    clean = "".join(ch.lower() if ch.isalnum() else "-" for ch in str(alias).strip())
    clean = clean.strip("-")
    while "--" in clean:
        clean = clean.replace("--", "-")
    return clean or "default"


def strategy_baseline_dir(
    strategy_name: str,
    *,
    baseline_root: str = DEFAULT_STRATEGY_BASELINE_ROOT,
    alias: str = "default",
) -> str:
    """Return the canonical directory for a registered single-strategy baseline."""
    if strategy_name not in STRATEGY_REGISTRY:
        raise KeyError(f"Unknown strategy: {strategy_name}")
    return os.path.abspath(os.path.join(baseline_root, strategy_name, _normalize_baseline_alias(alias)))


def _load_json_object(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def resolve_registered_baseline_artifacts(
    strategy_name: str,
    *,
    baseline_root: str = DEFAULT_STRATEGY_BASELINE_ROOT,
    alias: str = "default",
) -> Optional[Dict[str, str]]:
    """Locate the canonical baseline artifacts for a strategy alias."""
    report_dir = strategy_baseline_dir(strategy_name, baseline_root=baseline_root, alias=alias)
    json_path = os.path.join(report_dir, "historical_baseline.json")
    if not os.path.exists(json_path):
        return None

    artifacts = {"json": os.path.abspath(json_path)}
    markdown_path = os.path.join(report_dir, "historical_baseline.md")
    registry_path = os.path.join(report_dir, "baseline_registry.json")
    if os.path.exists(markdown_path):
        artifacts["markdown"] = os.path.abspath(markdown_path)
    if os.path.exists(registry_path):
        artifacts["registry"] = os.path.abspath(registry_path)
    return artifacts


def register_strategy_baseline(
    snapshot: Dict[str, Any],
    *,
    baseline_root: str = DEFAULT_STRATEGY_BASELINE_ROOT,
    alias: str = "default",
) -> Dict[str, str]:
    """Register a canonical single-strategy baseline for later admission runs."""
    strategy_name = str(snapshot.get("strategy"))
    report_dir = strategy_baseline_dir(strategy_name, baseline_root=baseline_root, alias=alias)
    artifacts = write_baseline_artifacts(report_dir, snapshot)
    registry_payload = {
        "strategy": strategy_name,
        "strategy_family": snapshot.get("strategy_family"),
        "generated_at": snapshot.get("generated_at"),
        "alias": _normalize_baseline_alias(alias),
        "params": snapshot.get("params", {}),
        "params_signature": snapshot.get("params_signature") or compute_params_signature(snapshot.get("params", {})),
        "coverage": snapshot.get("coverage", {}),
        "sample_count": len(snapshot.get("samples", [])),
        "sample_ids": [sample.get("sample", {}).get("sample_id") for sample in snapshot.get("samples", [])],
        "artifacts": artifacts,
    }
    artifacts["registry"] = write_json(os.path.join(report_dir, "baseline_registry.json"), registry_payload)
    return artifacts


def resolve_baseline_snapshot(
    strategy_name: str,
    *,
    baseline_file: Optional[str] = None,
    baseline_root: str = DEFAULT_STRATEGY_BASELINE_ROOT,
    alias: str = "default",
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """Resolve an explicit or registered baseline snapshot for admission checks."""
    if baseline_file:
        path = os.path.abspath(baseline_file)
        return _load_json_object(path), {
            "mode": "explicit_file",
            "path": path,
            "alias": None,
            "registry": None,
        }

    artifacts = resolve_registered_baseline_artifacts(
        strategy_name,
        baseline_root=baseline_root,
        alias=alias,
    )
    if not artifacts:
        return None, {
            "mode": "missing",
            "path": None,
            "alias": _normalize_baseline_alias(alias),
            "registry": None,
        }

    return _load_json_object(artifacts["json"]), {
        "mode": "strategy_registry",
        "path": artifacts["json"],
        "alias": _normalize_baseline_alias(alias),
        "registry": artifacts.get("registry"),
    }


def load_sample_cases(path: Optional[str] = None) -> List[HistoricalSampleCase]:
    """Load historical sample cases from YAML/JSON, or return defaults."""
    if not path:
        return list(DEFAULT_HISTORICAL_SAMPLE_CASES)

    with open(path, "r", encoding="utf-8") as handle:
        if path.lower().endswith((".yaml", ".yml")):
            payload = yaml.safe_load(handle) or []
        else:
            payload = json.load(handle)

    if not isinstance(payload, list):
        raise ValueError("Sample case file must contain a list of sample definitions.")
    return [HistoricalSampleCase.from_dict(item) for item in payload]


def filter_sample_cases(
    strategy_name: str,
    sample_cases: Sequence[HistoricalSampleCase],
    sample_ids: Optional[Iterable[str]] = None,
    regimes: Optional[Iterable[str]] = None,
) -> List[HistoricalSampleCase]:
    """Pick applicable sample cases for a strategy."""
    if strategy_name not in STRATEGY_REGISTRY:
        raise KeyError(f"Unknown strategy: {strategy_name}")

    module = STRATEGY_REGISTRY[strategy_name]
    selected = list(sample_cases)

    if sample_ids:
        wanted = {sample_id.strip() for sample_id in sample_ids if sample_id}
        selected = [case for case in selected if case.sample_id in wanted]

    if not selected:
        raise ValueError("No sample cases selected.")

    strategy_tag = "multi" if module.multi_symbol else "single"
    selected = [case for case in selected if strategy_tag in case.tags or not case.tags] or selected

    if regimes:
        wanted = {regime.strip().lower() for regime in regimes if regime}
        selected = [
            case
            for case in selected
            if wanted.intersection({tag.lower() for tag in case.tags})
        ]

    if not selected:
        raise ValueError("No sample cases matched the selected strategy shape or regime filters.")
    return selected


def _extract_regimes(tags: Sequence[str]) -> List[str]:
    """Extract normalized regime tags from a sample tag list."""
    tag_set = {tag.lower() for tag in tags}
    return [regime for regime in REGIME_TAGS if regime in tag_set]


def _summarize_sample_coverage(samples: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Summarize sample coverage across regime buckets."""
    regime_counts = {regime: 0 for regime in REGIME_TAGS}
    for sample in samples:
        for regime in _extract_regimes(sample.get("sample", {}).get("tags", [])):
            regime_counts[regime] += 1
    return {
        "sample_count": len(samples),
        "covered_regimes": [regime for regime, count in regime_counts.items() if count > 0],
        "regime_counts": regime_counts,
    }


def _build_regime_summary(sample_reports: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Aggregate admission outcomes by regime."""
    summary: Dict[str, Dict[str, Any]] = {}
    for regime in REGIME_TAGS:
        regime_reports = [
            report
            for report in sample_reports
            if regime in _extract_regimes(report.get("sample", {}).get("tags", []))
        ]
        if not regime_reports:
            continue
        statuses = [report.get("status", "FAIL") for report in regime_reports]
        summary[regime] = {
            "sample_count": len(regime_reports),
            "pass_count": sum(status == "PASS" for status in statuses),
            "watch_count": sum(status == "WATCH" for status in statuses),
            "fail_count": sum(status == "FAIL" for status in statuses),
            "mean_sharpe": _safe_mean([report.get("metrics", {}).get("sharpe") for report in regime_reports]),
            "mean_cum_return": _safe_mean(
                [report.get("metrics", {}).get("cum_return") for report in regime_reports]
            ),
            "max_mdd": _safe_max([report.get("metrics", {}).get("mdd") for report in regime_reports]),
        }
    return summary


def _nav_signature(nav: pd.Series) -> Optional[str]:
    """Return a deterministic NAV fingerprint."""
    if nav is None or len(nav) == 0:
        return None
    clean = nav.copy()
    clean.index = pd.to_datetime(clean.index)
    clean = clean.sort_index()
    hashed = pd.util.hash_pandas_object(clean, index=True).values
    return hashlib.sha256(hashed.tobytes()).hexdigest()


def _trim_metrics(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Keep only durable numeric metrics for baseline/admission comparisons."""
    out: Dict[str, Any] = {}
    for key in TRACKED_METRICS:
        if key in metrics:
            try:
                out[key] = float(metrics[key])
            except Exception:
                out[key] = metrics[key]
    if metrics.get("error"):
        out["error"] = str(metrics["error"])
    return out


def _build_quality_summary(quality_report: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not quality_report:
        return {}
    summary = quality_report.get("summary", {}) if isinstance(quality_report, dict) else {}
    per_symbol = quality_report.get("per_symbol", {}) if isinstance(quality_report, dict) else {}
    return {
        "summary": _to_builtin(summary),
        "per_symbol": _to_builtin(per_symbol),
    }


def _run_case(
    strategy_name: str,
    case: HistoricalSampleCase,
    *,
    params: Optional[Dict[str, Any]],
    cash: float,
    commission: float,
    slippage: float,
    cache_dir: str,
    runner: Optional[StrategyRunner] = None,
) -> Dict[str, Any]:
    """Execute one sample case and return a normalized snapshot."""
    if runner is None:
        from src.backtest.engine import BacktestEngine

        runner = BacktestEngine(
            source=case.source,
            benchmark_source=case.benchmark_source or case.source,
            cache_dir=cache_dir,
            calendar_mode=case.calendar,
        )

    raw = runner.run_strategy(
        strategy_name,
        case.symbols,
        case.start,
        case.end,
        params=params,
        cash=cash,
        commission=commission,
        slippage=slippage,
        benchmark=case.benchmark,
        adj=case.adj,
        calendar_mode=case.calendar,
        collect_diagnostics=True,
    )
    nav = raw.pop("nav", None)
    raw.pop("_cerebro", None)
    quality_report = raw.pop("_quality_report", None)
    data_fingerprint = raw.pop("_data_fingerprint", None)

    nav_rows = int(len(nav)) if nav is not None else 0
    nav_start = None
    nav_end = None
    nav_final = None
    if nav is not None and len(nav) > 0:
        nav_start = str(pd.to_datetime(nav.index[0]).date())
        nav_end = str(pd.to_datetime(nav.index[-1]).date())
        nav_final = float(nav.iloc[-1])

    return {
        "sample": case.to_dict(),
        "run": {
            "metrics": _trim_metrics(raw),
            "quality": _build_quality_summary(quality_report),
            "data_fingerprint": _to_builtin(data_fingerprint),
            "nav_summary": {
                "rows": nav_rows,
                "start": nav_start,
                "end": nav_end,
                "final_nav": nav_final,
                "signature": _nav_signature(nav) if nav is not None else None,
            },
        },
    }


def generate_historical_baseline(
    strategy_name: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    sample_cases: Optional[Sequence[HistoricalSampleCase]] = None,
    sample_ids: Optional[Iterable[str]] = None,
    regimes: Optional[Iterable[str]] = None,
    cash: float = 200000,
    commission: float = 0.0001,
    slippage: float = 0.0005,
    cache_dir: str = "./cache",
    runner: Optional[StrategyRunner] = None,
    source_override: Optional[str] = None,
    benchmark_source_override: Optional[str] = None,
    calendar_override: Optional[str] = None,
    adj_override: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate a real-history regression baseline snapshot for a strategy."""
    base_cases = list(sample_cases) if sample_cases is not None else list(DEFAULT_HISTORICAL_SAMPLE_CASES)
    selected_cases = filter_sample_cases(strategy_name, base_cases, sample_ids, regimes)
    cases = [
        case.with_overrides(
            source=source_override,
            benchmark_source=benchmark_source_override,
            calendar=calendar_override,
            adj=adj_override,
        )
        for case in selected_cases
    ]

    results = [
        _run_case(
            strategy_name,
            case,
            params=params,
            cash=cash,
            commission=commission,
            slippage=slippage,
            cache_dir=cache_dir,
            runner=runner,
        )
        for case in cases
    ]

    return _to_builtin(
        {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "strategy": strategy_name,
            "strategy_family": get_strategy_family(strategy_name),
            "params": params or {},
            "params_signature": compute_params_signature(params or {}),
            "cash": cash,
            "commission": commission,
            "slippage": slippage,
            "cache_dir": cache_dir,
            "samples": results,
            "coverage": _summarize_sample_coverage(results),
        }
    )


def render_baseline_markdown(snapshot: Dict[str, Any]) -> str:
    """Render a markdown summary for a historical regression baseline snapshot."""
    lines = [
        "# 历史样本回归基线",
        "",
        f"- 生成时间: {snapshot.get('generated_at', '-')}",
        f"- 策略: `{snapshot.get('strategy', '-')}`",
        f"- 策略族: `{snapshot.get('strategy_family', '-')}`",
        f"- 参数签名: `{snapshot.get('params_signature', '-')}`",
        f"- 样本数量: {len(snapshot.get('samples', []))}",
        f"- 初始资金: {_fmt(snapshot.get('cash'), decimals=2)}",
        f"- 手续费: {_fmt_pct(snapshot.get('commission'), decimals=4)}",
        f"- 滑点: {_fmt_pct(snapshot.get('slippage'), decimals=4)}",
        "",
    ]

    coverage = snapshot.get("coverage", {})
    covered_regimes = coverage.get("covered_regimes", [])
    if covered_regimes:
        lines.extend(
            [
                "## Regime 覆盖",
                "",
                f"- 已覆盖: {', '.join(covered_regimes)}",
                "",
                "| Regime | 样本数 |",
                "|---|---:|",
            ]
        )
        for regime in REGIME_TAGS:
            lines.append(f"| {regime} | {coverage.get('regime_counts', {}).get(regime, 0)} |")
        lines.append("")

    for sample in snapshot.get("samples", []):
        meta = sample.get("sample", {})
        run = sample.get("run", {})
        metrics = run.get("metrics", {})
        quality = run.get("quality", {}).get("summary", {})
        nav_summary = run.get("nav_summary", {})
        lines.extend(
            [
                f"## 样本 `{meta.get('sample_id', '-')}`",
                "",
                f"- 描述: {meta.get('description', '-')}",
                f"- 区间: {meta.get('start', '-')} -> {meta.get('end', '-')}",
                f"- 标的: {', '.join(meta.get('symbols', []))}",
                f"- 数据源: `{meta.get('source', '-')}`",
                f"- 基准: `{meta.get('benchmark', '-')}`",
                f"- Regime: {', '.join(_extract_regimes(meta.get('tags', [])) or ['mixed'])}",
                "",
                "| 指标 | 数值 |",
                "|---|---:|",
                f"| 累计收益 | {_fmt_pct(metrics.get('cum_return'))} |",
                f"| Sharpe | {_fmt(metrics.get('sharpe'))} |",
                f"| 最大回撤 | {_fmt_pct(metrics.get('mdd'))} |",
                f"| Calmar | {_fmt(metrics.get('calmar'))} |",
                f"| Trades | {_fmt(metrics.get('trades'), decimals=0)} |",
                f"| NAV 行数 | {nav_summary.get('rows', 0)} |",
                f"| NAV 终值 | {_fmt(nav_summary.get('final_nav'))} |",
                f"| 平均缺失率 | {_fmt_pct(quality.get('avg_missing_ratio'))} |",
                "",
            ]
        )

    return "\n".join(lines).strip() + "\n"


def _compare_metric(
    current_value: Any,
    baseline_value: Any,
    tolerance: RegressionTolerance,
) -> Dict[str, Any]:
    """Compare one metric against the baseline."""
    try:
        current = float(current_value)
        baseline = float(baseline_value)
    except Exception:
        return {
            "status": "watch" if tolerance.severity == "warning" else "fail",
            "reason": "non_numeric",
            "current": current_value,
            "baseline": baseline_value,
        }

    delta = current - baseline
    allowed_candidates = [val for val in [tolerance.absolute] if val is not None]
    if tolerance.relative is not None:
        allowed_candidates.append(abs(baseline) * tolerance.relative)
    allowed = max(allowed_candidates) if allowed_candidates else 0.0
    passed = abs(delta) <= allowed
    return {
        "status": "pass" if passed else ("watch" if tolerance.severity == "warning" else "fail"),
        "severity": tolerance.severity,
        "current": current,
        "baseline": baseline,
        "delta": delta,
        "allowed_delta": allowed,
    }


def _gate_status(checks: Sequence[Dict[str, Any]]) -> str:
    """Reduce check results to PASS/WATCH/FAIL."""
    statuses = {check["status"] for check in checks}
    if "fail" in statuses:
        return "FAIL"
    if "watch" in statuses:
        return "WATCH"
    return "PASS"


def _metric_check(label: str, actual: float, expected: str, passed: bool, *, severity: str = "required") -> Dict[str, Any]:
    status = "pass" if passed else ("watch" if severity == "warning" else "fail")
    return {
        "label": label,
        "actual": actual,
        "expected": expected,
        "severity": severity,
        "status": status,
    }


def _coerce_float(value: Any) -> float:
    """Convert metric inputs to float, treating missing/non-numeric values as NaN."""
    try:
        return float(value)
    except Exception:
        return float("nan")


def _evaluate_quality_checks(quality: Dict[str, Any], profile: AdmissionProfile) -> List[Dict[str, Any]]:
    checks: List[Dict[str, Any]] = []
    summary = quality.get("summary", {}) if isinstance(quality, dict) else {}
    avg_missing_ratio = float(summary.get("avg_missing_ratio", 0.0) or 0.0)
    checks.append(
        _metric_check(
            "Average missing ratio",
            avg_missing_ratio,
            f"<= {profile.max_avg_missing_ratio:.2%}",
            avg_missing_ratio <= profile.max_avg_missing_ratio,
        )
    )

    per_symbol = quality.get("per_symbol", {}) if isinstance(quality, dict) else {}
    for symbol, row in per_symbol.items():
        missing_ratio = float(row.get("missing_ratio", 0.0) or 0.0)
        duplicate_rows = int(row.get("duplicate_rows", 0) or 0)
        nan_rows = int(row.get("nan_rows", 0) or 0)
        ohlc_anomalies = int(row.get("ohlc_anomalies", 0) or 0)
        checks.extend(
            [
                _metric_check(
                    f"{symbol} missing ratio",
                    missing_ratio,
                    f"<= {profile.max_symbol_missing_ratio:.2%}",
                    missing_ratio <= profile.max_symbol_missing_ratio,
                ),
                _metric_check(
                    f"{symbol} duplicate rows",
                    duplicate_rows,
                    f"<= {profile.max_duplicate_rows}",
                    duplicate_rows <= profile.max_duplicate_rows,
                ),
                _metric_check(
                    f"{symbol} NaN rows",
                    nan_rows,
                    f"<= {profile.max_nan_rows}",
                    nan_rows <= profile.max_nan_rows,
                ),
                _metric_check(
                    f"{symbol} OHLC anomalies",
                    ohlc_anomalies,
                    f"<= {profile.max_ohlc_anomalies}",
                    ohlc_anomalies <= profile.max_ohlc_anomalies,
                ),
            ]
        )
    return checks


def _evaluate_metric_checks(metrics: Dict[str, Any], profile: AdmissionProfile) -> List[Dict[str, Any]]:
    checks: List[Dict[str, Any]] = []
    error = metrics.get("error")
    if error:
        checks.append(
            {
                "label": "Strategy runtime error",
                "actual": str(error),
                "expected": "no runtime error",
                "severity": "required",
                "status": "fail",
            }
        )
        return checks

    sharpe = _coerce_float(metrics.get("sharpe", float("nan")))
    mdd = _coerce_float(metrics.get("mdd", float("nan")))
    calmar = _coerce_float(metrics.get("calmar", float("nan")))
    trades = _coerce_float(metrics.get("trades", float("nan")))
    profit_factor = _coerce_float(metrics.get("profit_factor", float("nan")))
    win_rate = _coerce_float(metrics.get("win_rate", float("nan")))
    expectancy = _coerce_float(metrics.get("expectancy", float("nan")))

    checks.extend(
        [
            _metric_check("Sharpe", sharpe, f">= {profile.min_sharpe:.2f}", sharpe >= profile.min_sharpe),
            _metric_check("Max drawdown", mdd, f"<= {profile.max_mdd:.2%}", mdd <= profile.max_mdd),
            _metric_check("Calmar", calmar, f">= {profile.min_calmar:.2f}", calmar >= profile.min_calmar),
            _metric_check("Trades", trades, f">= {profile.min_trades}", trades >= profile.min_trades),
            _metric_check(
                "Profit factor",
                profit_factor,
                f">= {profile.min_profit_factor:.2f}",
                profit_factor >= profile.min_profit_factor,
            ),
            _metric_check("Win rate", win_rate, f">= {profile.min_win_rate:.2%}", win_rate >= profile.min_win_rate, severity="warning"),
            _metric_check(
                "Expectancy",
                expectancy,
                f">= {profile.min_expectancy:.4f}",
                expectancy >= profile.min_expectancy,
                severity="warning",
            ),
        ]
    )
    return checks


def evaluate_admission(
    current_snapshot: Dict[str, Any],
    *,
    profile_name: str = "institutional",
    baseline_snapshot: Optional[Dict[str, Any]] = None,
    baseline_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Evaluate a current run snapshot against admission gates and optional baseline."""
    strategy_name = str(current_snapshot.get("strategy"))
    strategy_family, profile = resolve_admission_profile(strategy_name, profile_name)
    current_params_signature = str(
        current_snapshot.get("params_signature") or compute_params_signature(current_snapshot.get("params", {}))
    )
    baseline_map = {}
    baseline_generated_at = None
    baseline_params_signature = None
    baseline_params_match = None
    baseline_usable_for_regression = False
    if baseline_snapshot:
        baseline_generated_at = baseline_snapshot.get("generated_at")
        baseline_params_signature = str(
            baseline_snapshot.get("params_signature") or compute_params_signature(baseline_snapshot.get("params", {}))
        )
        baseline_params_match = baseline_params_signature == current_params_signature
        baseline_usable_for_regression = bool(baseline_params_match)
        baseline_map = {
            sample["sample"]["sample_id"]: sample
            for sample in baseline_snapshot.get("samples", [])
        }

    sample_reports: List[Dict[str, Any]] = []
    for sample in current_snapshot.get("samples", []):
        sample_id = sample["sample"]["sample_id"]
        run = sample.get("run", {})
        metrics = run.get("metrics", {})
        quality = run.get("quality", {})

        metric_checks = _evaluate_metric_checks(metrics, profile)
        quality_checks = _evaluate_quality_checks(quality, profile) if quality else []
        regression_checks: Dict[str, Any] = {}

        baseline_sample = baseline_map.get(sample_id)
        if baseline_sample and baseline_usable_for_regression:
            baseline_metrics = baseline_sample.get("run", {}).get("metrics", {})
            for metric_name, tolerance in profile.regression_tolerances.items():
                if metric_name in metrics and metric_name in baseline_metrics:
                    regression_checks[metric_name] = _compare_metric(
                        metrics[metric_name],
                        baseline_metrics[metric_name],
                        tolerance,
                    )

        checks = metric_checks + quality_checks + list(regression_checks.values())
        sample_reports.append(
            {
                "sample": sample["sample"],
                "status": _gate_status(checks),
                "metrics": metrics,
                "quality": quality,
                "metric_checks": metric_checks,
                "quality_checks": quality_checks,
                "regression_checks": regression_checks,
                "baseline_metrics": baseline_sample.get("run", {}).get("metrics", {}) if baseline_sample else {},
            }
        )

    aggregate = {
        "sample_count": len(sample_reports),
        "mean_sharpe": _safe_mean([report["metrics"].get("sharpe") for report in sample_reports]),
        "mean_cum_return": _safe_mean([report["metrics"].get("cum_return") for report in sample_reports]),
        "max_mdd": _safe_max([report["metrics"].get("mdd") for report in sample_reports]),
        "total_trades": int(
            sum(float(report["metrics"].get("trades", 0.0) or 0.0) for report in sample_reports)
        ),
    }

    overall_status = _gate_status([{"status": report["status"].lower()} for report in sample_reports]) if sample_reports else "FAIL"
    recommendation = {
        "PASS": "可进入下一阶段（仿真/组合评审），但仍需与组合层风险约束联动。",
        "WATCH": "仅限研究或纸上环境，需先处理预警项后再申请准入。",
        "FAIL": "当前不具备准入条件，需修复数据/策略问题并重跑基线。",
    }[overall_status]

    return _to_builtin(
        {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "strategy": strategy_name,
            "strategy_family": strategy_family,
            "params": current_snapshot.get("params", {}),
            "params_signature": current_params_signature,
            "profile_level": profile_name,
            "profile": asdict(profile),
            "baseline_generated_at": baseline_generated_at,
            "baseline": {
                "mode": (baseline_context or {}).get("mode", "missing" if baseline_snapshot is None else "unknown"),
                "path": (baseline_context or {}).get("path"),
                "alias": (baseline_context or {}).get("alias"),
                "registry": (baseline_context or {}).get("registry"),
                "generated_at": baseline_generated_at,
                "params_match": baseline_params_match,
                "usable_for_regression": baseline_usable_for_regression,
                "current_params_signature": current_params_signature,
                "baseline_params_signature": baseline_params_signature,
            },
            "overall_status": overall_status,
            "aggregate": aggregate,
            "coverage": current_snapshot.get("coverage", {}),
            "regime_summary": _build_regime_summary(sample_reports),
            "samples": sample_reports,
            "recommendation": recommendation,
        }
    )


def _safe_mean(values: Sequence[Any]) -> Optional[float]:
    nums: List[float] = []
    for value in values:
        try:
            number = float(value)
        except Exception:
            continue
        if math.isnan(number) or math.isinf(number):
            continue
        nums.append(number)
    return float(sum(nums) / len(nums)) if nums else None


def _safe_max(values: Sequence[Any]) -> Optional[float]:
    nums: List[float] = []
    for value in values:
        try:
            number = float(value)
        except Exception:
            continue
        if math.isnan(number) or math.isinf(number):
            continue
        nums.append(number)
    return max(nums) if nums else None


def render_admission_markdown(report: Dict[str, Any]) -> str:
    """Render a markdown strategy admission report."""
    lines = [
        "# 策略准入报告",
        "",
        f"- 生成时间: {report.get('generated_at', '-')}",
        f"- 策略: `{report.get('strategy', '-')}`",
        f"- 策略族: `{report.get('strategy_family', '-')}`",
        f"- 参数签名: `{report.get('params_signature', '-')}`",
        f"- 请求档位: `{report.get('profile_level', '-')}`",
        f"- 实际模板: `{report.get('profile', {}).get('name', '-')}`",
        f"- 总体结论: **{report.get('overall_status', 'FAIL')}**",
        f"- 建议: {report.get('recommendation', '-')}",
        "",
        "## 汇总",
        "",
        "| 指标 | 数值 |",
        "|---|---:|",
        f"| 样本数量 | {report.get('aggregate', {}).get('sample_count', 0)} |",
        f"| 平均 Sharpe | {_fmt(report.get('aggregate', {}).get('mean_sharpe'))} |",
        f"| 平均累计收益 | {_fmt_pct(report.get('aggregate', {}).get('mean_cum_return'))} |",
        f"| 最差最大回撤 | {_fmt_pct(report.get('aggregate', {}).get('max_mdd'))} |",
        f"| 总交易次数 | {report.get('aggregate', {}).get('total_trades', 0)} |",
        "",
    ]

    coverage = report.get("coverage", {})
    if coverage:
        lines.extend(
            [
                "## Regime 覆盖",
                "",
                f"- 已覆盖 regime: {', '.join(coverage.get('covered_regimes', [])) or '无'}",
                "",
                "| Regime | 样本数 |",
                "|---|---:|",
            ]
        )
        for regime in REGIME_TAGS:
            lines.append(f"| {regime} | {coverage.get('regime_counts', {}).get(regime, 0)} |")
        lines.append("")

    regime_summary = report.get("regime_summary", {})
    if regime_summary:
        lines.extend(
            [
                "## Regime 表现",
                "",
                "| Regime | 样本数 | PASS | WATCH | FAIL | 平均 Sharpe | 平均累计收益 | 最差最大回撤 |",
                "|---|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for regime in REGIME_TAGS:
            row = regime_summary.get(regime)
            if not row:
                continue
            lines.append(
                f"| {regime} | {row.get('sample_count', 0)} | {row.get('pass_count', 0)} | "
                f"{row.get('watch_count', 0)} | {row.get('fail_count', 0)} | "
                f"{_fmt(row.get('mean_sharpe'))} | {_fmt_pct(row.get('mean_cum_return'))} | "
                f"{_fmt_pct(row.get('max_mdd'))} |"
            )
        lines.append("")

    baseline = report.get("baseline", {})
    if baseline:
        lines.extend(
            [
                "## 回归基线",
                "",
                f"- 基线来源: `{baseline.get('mode', '-')}`",
                f"- 基线生成时间: {baseline.get('generated_at') or '-'}",
                f"- 基线路径: `{baseline.get('path') or '-'}`",
                f"- 基线别名: `{baseline.get('alias') or '-'}`",
                f"- 参数匹配: {'是' if baseline.get('params_match') else ('否' if baseline.get('params_match') is False else '-')}",
                f"- 漂移检查: {'已启用' if baseline.get('usable_for_regression') else '未启用'}",
                "",
            ]
        )

    for sample in report.get("samples", []):
        meta = sample.get("sample", {})
        metrics = sample.get("metrics", {})
        lines.extend(
            [
                f"## 样本 `{meta.get('sample_id', '-')}`",
                "",
                f"- 描述: {meta.get('description', '-')}",
                f"- 区间: {meta.get('start', '-')} -> {meta.get('end', '-')}",
                f"- 标的: {', '.join(meta.get('symbols', []))}",
                f"- Regime: {', '.join(_extract_regimes(meta.get('tags', [])) or ['mixed'])}",
                f"- 结论: **{sample.get('status', 'FAIL')}**",
                "",
                "### 核心指标",
                "",
                "| 指标 | 当前值 |",
                "|---|---:|",
                f"| 累计收益 | {_fmt_pct(metrics.get('cum_return'))} |",
                f"| Sharpe | {_fmt(metrics.get('sharpe'))} |",
                f"| 最大回撤 | {_fmt_pct(metrics.get('mdd'))} |",
                f"| Calmar | {_fmt(metrics.get('calmar'))} |",
                f"| 胜率 | {_fmt_pct(metrics.get('win_rate'))} |",
                f"| Profit Factor | {_fmt(metrics.get('profit_factor'))} |",
                f"| Expectancy | {_fmt(metrics.get('expectancy'))} |",
                f"| Trades | {_fmt(metrics.get('trades'), decimals=0)} |",
                "",
                "### 准入检查",
                "",
                "| 检查项 | 实际值 | 期望 | 严重级别 | 结果 |",
                "|---|---:|---|---|---|",
            ]
        )
        for check in sample.get("metric_checks", []) + sample.get("quality_checks", []):
            actual = check.get("actual")
            if "rate" in check.get("label", "").lower() or "drawdown" in check.get("label", "").lower():
                actual_text = _fmt_pct(actual) if isinstance(actual, (int, float)) else str(actual)
            else:
                actual_text = _fmt(actual) if isinstance(actual, (int, float)) else str(actual)
            lines.append(
                f"| {check.get('label')} | {actual_text} | {check.get('expected')} | "
                f"{check.get('severity')} | {check.get('status').upper()} |"
            )

        regression_checks = sample.get("regression_checks", {})
        if regression_checks:
            lines.extend(
                [
                    "",
                    "### 基线漂移",
                    "",
                    "| 指标 | 当前值 | 基线值 | 偏差 | 容许偏差 | 结果 |",
                    "|---|---:|---:|---:|---:|---|",
                ]
            )
            for metric_name, check in regression_checks.items():
                current = check.get("current")
                baseline = check.get("baseline")
                delta = check.get("delta")
                allowed = check.get("allowed_delta")
                if metric_name in {"cum_return", "mdd", "win_rate", "bench_return", "bench_mdd", "excess_return"}:
                    cur_txt = _fmt_pct(current)
                    base_txt = _fmt_pct(baseline)
                    delta_txt = _fmt_pct(delta)
                    allowed_txt = _fmt_pct(allowed)
                else:
                    cur_txt = _fmt(current)
                    base_txt = _fmt(baseline)
                    delta_txt = _fmt(delta)
                    allowed_txt = _fmt(allowed)
                lines.append(
                    f"| {metric_name} | {cur_txt} | {base_txt} | {delta_txt} | {allowed_txt} | {check.get('status').upper()} |"
                )
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def write_json(path: str, payload: Dict[str, Any]) -> str:
    """Write JSON artifact to disk."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(_to_builtin(payload), handle, indent=2, ensure_ascii=False, allow_nan=False)
    return os.path.abspath(path)


def write_markdown(path: str, content: str) -> str:
    """Write markdown artifact to disk."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    return os.path.abspath(path)


def write_admission_artifacts(report_dir: str, report: Dict[str, Any]) -> Dict[str, str]:
    """Persist strategy admission report as JSON + Markdown."""
    os.makedirs(report_dir, exist_ok=True)
    return {
        "json": write_json(os.path.join(report_dir, "strategy_admission.json"), report),
        "markdown": write_markdown(os.path.join(report_dir, "strategy_admission.md"), render_admission_markdown(report)),
    }


def write_baseline_artifacts(
    report_dir: str,
    snapshot: Dict[str, Any],
    *,
    prefix: str = "historical_baseline",
) -> Dict[str, str]:
    """Persist historical regression baseline as JSON + Markdown."""
    os.makedirs(report_dir, exist_ok=True)
    return {
        "json": write_json(os.path.join(report_dir, f"{prefix}.json"), snapshot),
        "markdown": write_markdown(
            os.path.join(report_dir, f"{prefix}.md"),
            render_baseline_markdown(snapshot),
        ),
    }


def _fmt(value: Any, decimals: int = 4) -> str:
    try:
        number = float(value)
    except Exception:
        return "N/A" if value is None else str(value)
    if math.isnan(number) or math.isinf(number):
        return "N/A"
    return f"{number:.{decimals}f}"


def _fmt_pct(value: Any, decimals: int = 2) -> str:
    try:
        number = float(value)
    except Exception:
        return "N/A" if value is None else str(value)
    if math.isnan(number) or math.isinf(number):
        return "N/A"
    return f"{number * 100:.{decimals}f}%"
