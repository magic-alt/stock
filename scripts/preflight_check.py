#!/usr/bin/env python3
"""
Comprehensive preflight check script for production launch.

It validates:
- Basic process health checks (directories/db/dependencies/providers/IO)
- Strategy availability and run-time configuration sanity
- Optional backtest smoke test
- Optional paper trading smoke replay (for strategy consistency check)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.config import ConfigManager
from src.core.events import EventEngine
from src.core.logger import get_logger
from src.core.reconciliation import Reconciler
from src.core.paper_runner_v3 import run_paper_v3
from src.core.trading_gateway import BrokerType
from src.data_sources.providers import get_provider
from src.backtest.engine import BacktestEngine
from src.backtest.strategy_modules import STRATEGY_REGISTRY
from scripts.health_check import HealthChecker
from src.strategies.backtrader_registry import resolve_strategy_name
from src.strategies.unified_strategies import (
    UnifiedBollingerStrategy,
    UnifiedEMAStrategy,
    UnifiedMACDStrategy,
)

logger = get_logger("preflight_check")


@dataclass
class PreflightCheck:
    name: str
    status: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


MIN_ALIGNMENT_POINTS = 5
DEFAULT_ALIGNMENT_THRESHOLD = 0.03
DEFAULT_ALIGNMENT_FAIL_THRESHOLD = 0.10
MIN_TRADE_COUNT_FOR_ADVICE = 5
DRIFT_GAP_TRADE_RATIO_WARNING = 0.35


def _resolve_strategy_name(strategy: str) -> Tuple[str, str, bool]:
    """Resolve alias strategy names to canonical backtest names.

    Returns:
        Tuple of (resolved_name, requested_name, alias_resolved)
    """
    requested = (strategy or "").strip().lower()
    if not requested:
        requested = "macd"
    resolved = resolve_strategy_name(requested)

    if resolved in STRATEGY_REGISTRY:
        return resolved, requested, resolved != requested

    # 回退到原始名称，保证用户输入错误时仍可给出清晰失败信息
    return requested, requested, False


def _to_list(value: Optional[Sequence[str]]) -> List[str]:
    """Normalize symbol inputs."""
    if not value:
        return []
    symbols: List[str] = []
    for item in value:
        if "," in item:
            symbols.extend([token.strip() for token in item.split(",") if token.strip()])
        else:
            cleaned = item.strip()
            if cleaned:
                symbols.append(cleaned)
    # dedupe while preserving order
    return list(dict.fromkeys(symbols))


def _default_symbol_list(config: ConfigManager, fallback: Optional[Sequence[str]] = None) -> List[str]:
    """Pick symbols from config first, fallback values next."""
    if config.strategy.symbols:
        return list(config.strategy.symbols)
    if fallback:
        return list(fallback)
    return ["600519.SH"]


def _to_float_or_none(value: Any) -> Optional[float]:
    """Convert values to float when possible."""
    if value is None:
        return None
    try:
        casted = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(casted) or pd.isinf(casted):
        return None
    return casted


def _safe_div(numer: Any, denom: Any) -> Optional[float]:
    """Return numer / denom when both are valid floats."""
    numer_value = _to_float_or_none(numer)
    denom_value = _to_float_or_none(denom)
    if numer_value is None or denom_value is None or denom_value == 0:
        return None
    return numer_value / denom_value


def _build_candidate_grids(
    strategy: str,
    unified_params: Dict[str, Any],
) -> Dict[str, Any]:
    """Generate compact, machine-consumable candidate parameters for next search round."""
    candidates: List[Dict[str, Any]] = []

    def _append(candidate: Dict[str, Any]) -> None:
        if candidate in candidates:
            return
        candidates.append(candidate)
        if len(candidates) >= 6:
            return

    if strategy == "ema":
        fast = max(2, int(unified_params.get("fast", 10)))
        slow = max(fast + 1, int(unified_params.get("slow", 30)))
        size = int(unified_params.get("size", 100))

        _append({"fast": max(2, fast - 2), "slow": max(slow - 4, fast + 2), "size": size})
        _append({"fast": max(2, fast - 1), "slow": max(slow - 2, fast + 3), "size": size})
        _append({"fast": fast, "slow": slow, "size": size})
        _append({"fast": min(20, fast + 1), "slow": min(40, slow + 3), "size": size})
        _append({"fast": max(2, fast - 1), "slow": min(40, slow + 6), "size": size})
        _append({"fast": min(18, fast + 2), "slow": min(45, slow + 4), "size": size})

    elif strategy == "macd":
        fast = int(unified_params.get("fast", 12))
        slow = int(unified_params.get("slow", 26))
        signal = int(unified_params.get("signal", 9))
        size = int(unified_params.get("size", 100))

        if fast >= slow:
            fast = max(3, slow - 1)
        if signal >= fast:
            signal = max(3, fast - 1)

        _append({"fast": fast, "slow": slow, "signal": signal, "size": size})
        _append({"fast": max(5, fast - 2), "slow": slow, "signal": min(max(5, signal - 1), 10), "size": size})
        _append({"fast": fast, "slow": slow + 4, "signal": signal, "size": size})
        _append({"fast": max(5, fast - 1), "slow": slow - 2, "signal": signal, "size": size})
        _append({"fast": fast, "slow": slow + 2, "signal": min(signal + 1, 12), "size": size})
        _append({"fast": fast, "slow": max(fast + 8, slow), "signal": max(6, signal - 1), "size": size})

    elif strategy == "bollinger":
        period = int(unified_params.get("period", 20))
        std_dev = _to_float_or_none(unified_params.get("std_dev")) or 2.0
        size = int(unified_params.get("size", 100))
        std_candidates = [max(1.6, round(std_dev - 0.3, 2)), max(1.4, round(std_dev - 0.1, 2)), std_dev, round(std_dev + 0.1, 2), round(std_dev + 0.3, 2)]
        period_candidates = [max(10, period - 2), max(12, period - 1), period, period + 2, period + 4]
        for p in period_candidates:
            for s in std_candidates:
                _append({"period": max(10, int(p)), "std_dev": round(float(s), 2), "size": size})

    else:
        candidates = []

    candidates = candidates[:6]
    return {
        "advice_level": "info",
        "candidate_grid": candidates,
        "max_candidates": len(candidates),
        "param_mode": "unified" if strategy in {"ema", "macd", "bollinger"} else "strategy-specific",
    }


def _build_strategy_advice(
    strategy: str,
    requested_params: Dict[str, Any],
    unified_params: Dict[str, Any],
    alignment: Dict[str, Any],
    backtest_metrics: Dict[str, Any],
    paper_metrics: Dict[str, Any],
    backtest_trades: int,
    paper_trades: int,
) -> Dict[str, Any]:
    """Build optimization suggestions from backtest-vs-paper comparison."""
    suggestions: List[str] = []
    level = "info"
    alignment_details = alignment.get("details", {})
    max_abs_diff = alignment_details.get("max_abs_diff")

    if max_abs_diff is None:
        return {
            "advice_level": "warn",
            "suggestions": ["缺少可用 NAV 样本，建议先核对数据可得性与字段齐全性。"],
            "candidate_params": {"parameter_plan": "retry_inputs"},
        }

    drift_threshold = _to_float_or_none(alignment_details.get("drift_threshold")) or DEFAULT_ALIGNMENT_THRESHOLD
    fail_threshold = _to_float_or_none(alignment_details.get("fail_threshold")) or DEFAULT_ALIGNMENT_FAIL_THRESHOLD
    drift = _to_float_or_none(max_abs_diff) or 0.0

    bt_return = _to_float_or_none(backtest_metrics.get("cum_return"))
    paper_return = _to_float_or_none(paper_metrics.get("total_return"))
    if paper_return is not None:
        paper_return = paper_return / 100.0

    if paper_return is not None and bt_return is not None:
        return_gap = paper_return - bt_return
        if abs(return_gap) <= drift_threshold * 0.5:
            suggestions.append(
                "回测与回放收益口径接近，可进入更严格的市场节假日/滑点压测。"
            )
        elif abs(return_gap) <= drift_threshold:
            suggestions.append("收益漂移在可接受范围边缘，建议先分批放量而非一次性实盘扩仓。")
        elif abs(return_gap) <= fail_threshold:
            suggestions.append("收益漂移偏大，建议做小步参数扰动并复跑预检。")
            level = "warn"
        else:
            suggestions.append(
                "收益漂移超阈值，请先下调仓位、修复参数耦合后再做实盘验证。"
            )
            level = "block"

        nav_corr = alignment_details.get("nav_corr")
        if nav_corr is not None and nav_corr < 0.5:
            suggestions.append("回测与回放收益相关性较低，建议增加信号确认与执行过滤。")

    if backtest_trades >= MIN_TRADE_COUNT_FOR_ADVICE:
        trade_ratio = _safe_div(paper_trades, backtest_trades)
        if trade_ratio is not None:
            if trade_ratio < (1 - DRIFT_GAP_TRADE_RATIO_WARNING):
                suggestions.append("实盘触发交易显著偏少，建议放宽阈值或缩短均线周期提高覆盖。")
                if level == "info":
                    level = "warn"
            elif trade_ratio > (1 + DRIFT_GAP_TRADE_RATIO_WARNING):
                suggestions.append(
                    "实盘触发交易显著偏多，建议增强 cooldown 或放宽开仓过滤避免过度交易。"
                )
                if level == "info":
                    level = "warn"

    if strategy == "ema":
        fast = int(unified_params.get("fast", 10))
        slow = int(unified_params.get("slow", 30))
        if slow - fast >= 40:
            suggestions.append("EMA 阶梯差过大，建议 slow 调回 20~40，或上调 fast。")
            level = "warn"
        if "period" in requested_params:
            suggestions.append("建议在实盘优化中用 fast/slow 替代 period，避免对齐偏差。")

    if strategy == "macd":
        fast = int(unified_params.get("fast", 12))
        slow = int(unified_params.get("slow", 26))
        signal = int(unified_params.get("signal", 9))
        if fast >= slow:
            suggestions.append("fast >= slow 不合理，请修正参数边界后再执行预检。")
            level = "block"
        if fast < 5 and signal > 12:
            suggestions.append("fast 太短且 signal 偏长，建议信号线缩短到 [7,12] 区间。")
            level = "warn"
        elif signal >= fast:
            suggestions.append("signal 与 fast 关系偏弱，建议先测试 [5,12] 信号窗口。")
            level = "warn"

    if strategy == "bollinger":
        std_dev = _to_float_or_none(unified_params.get("std_dev")) or 2.0
        period = int(unified_params.get("period", 20))
        if period < 12:
            suggestions.append("Bollinger period 太短，建议提升到 15~25 以抑制噪音。")
            level = "warn"
        if std_dev > 2.4:
            suggestions.append("std_dev 偏宽，建议测试 1.8~2.3 并观察漂移收敛。")
            level = "warn"

    if drift > fail_threshold:
        suggestions.append("建议暂停实盘放量，优先做 paper 重放参数 sweep。")
        level = "block"
    elif drift > drift_threshold:
        suggestions.append("建议以降仓和分级放量方式进入实盘，持续观察 7 个交易日漂移。")
        if level == "info":
            level = "warn"

    if not suggestions:
        suggestions.append("当前未触发明显异常，可结合风险指标进行下阶段参数网格。")

    unique: List[str] = []
    seen = set()
    for item in suggestions:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)

    sweep_plan = {
        "scope": "paper_replay_replay",
        "reason": "alignment_feedback",
        "recommendation": "rerun_with_sweep",
        "status": "block" if level == "block" else "continue_careful",
    }
    candidate_params = _build_candidate_grids(strategy=strategy, unified_params=unified_params)

    if level == "block":
        sweep_plan["status"] = "pause_before_market"
    elif level == "warn":
        sweep_plan["status"] = "limited_ramp"

    return {
        "advice_level": level,
        "suggestions": unique,
        "candidate_grid": candidate_params.get("candidate_grid", []),
        "candidate_plan": {
            "advice_level": level,
            "status": sweep_plan["status"],
            "reason": sweep_plan["reason"],
            "notes": [
                "参数网格用于 paper 重放",
                "每个候选请执行 3-5 日快速复检",
            ],
            "param_mode": candidate_params.get("param_mode", "unified"),
        },
    }


def _default_window(days: int = 90) -> Dict[str, str]:
    """Return a compact, fast smoke-test date window."""
    end_dt = datetime.now().date()
    start_dt = end_dt - timedelta(days=days)
    return {
        "start": start_dt.strftime("%Y-%m-%d"),
        "end": end_dt.strftime("%Y-%m-%d"),
    }


def _safe_run_backtest(
    strategy: str,
    symbols: List[str],
    start: str,
    end: str,
    *,
    source: str,
    cache_dir: str,
    cash: float,
    commission: float,
    slippage: float,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run lightweight backtest smoke and return normalized payload."""
    engine = BacktestEngine(source=source, cache_dir=cache_dir, calendar_mode="fill")
    strategy_metrics = engine.run_strategy(
        strategy=strategy,
        symbols=symbols,
        start=start,
        end=end,
        params=params,
        cash=cash,
        commission=commission,
        slippage=slippage,
        out_dir=None,
        collect_diagnostics=True,
    )

    nav = strategy_metrics.pop("nav", None)
    if isinstance(nav, pd.Series):
        nav = nav.astype(float)
    return {
        "ok": True,
        "metrics": strategy_metrics,
        "nav": nav,
    }


def _live_strategy_factory(strategy: str, params: Optional[Dict[str, Any]]) -> Any:
    """Return a unified paper-executable strategy instance for alignment checks."""
    params = params or {}

    if strategy == "ema":
        period = int(params.get("period", 20))
        period = max(2, period)
        fast = max(3, int(max(2, period // 2)))
        slow = max(fast + 1, period)
        return UnifiedEMAStrategy(fast=fast, slow=slow, size=100)

    if strategy == "macd":
        return UnifiedMACDStrategy(
            fast=int(params.get("fast", 12)),
            slow=int(params.get("slow", 26)),
            signal=int(params.get("signal", 9)),
            size=100,
        )

    if strategy == "bollinger":
        return UnifiedBollingerStrategy(
            period=int(params.get("period", 20)),
            std_dev=float(params.get("devfactor", 2.0)),
            size=100,
        )

    # Fallback: ensure preflight can still validate paper pipeline end-to-end.
    return UnifiedEMAStrategy(fast=10, slow=30, size=100)


def _safe_run_paper(
    strategy_name: str,
    params: Optional[Dict[str, Any]],
    symbols: List[str],
    start: str,
    end: str,
    *,
    source: str,
    cache_dir: str,
    cash: float,
    commission: float,
    slippage: float,
    adj: Optional[str] = None,
) -> Dict[str, Any]:
    provider = get_provider(source, cache_dir=cache_dir)
    data_map = provider.load_stock_daily(
        symbols=symbols,
        start=start,
        end=end,
        adj=adj,
        cache_dir=cache_dir,
    )

    cleaned: Dict[str, pd.DataFrame] = {}
    for symbol, df in data_map.items():
        if df is None or df.empty:
            continue
        df = df.copy()
        df = df.sort_index()
        required = {"open", "high", "low", "close", "volume"}
        if not required.issubset(set(df.columns)):
            continue
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        cleaned[symbol] = df

    if not cleaned:
        raise ValueError("No valid OHLCV data for paper simulation")

    strategy = _live_strategy_factory(strategy_name, params)
    events = EventEngine()
    result = run_paper_v3(
        strategy,
        cleaned,
        events=events,
        slippage=slippage,
        initial_cash=float(cash),
        commission_rate=float(commission),
    )

    nav = result.get("nav")
    if isinstance(nav, pd.Series):
        nav = nav.astype(float)
    return {
        "ok": True,
        "metrics": result.get("metrics", {}),
        "nav": nav,
        "account": result.get("account", {}),
        "trades": result.get("trades", []),
    }


def _build_unified_strategy_params(strategy: str, params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Build unified strategy params for paper replay with sane parameter adaptation."""
    params = params or {}
    normalized = {k: v for k, v in params.items()}

    if strategy == "ema":
        if "fast" in normalized and "slow" in normalized:
            fast = int(normalized.get("fast", 10))
            slow = int(normalized.get("slow", 30))
        else:
            period = int(normalized.get("period", 20))
            fast = int(normalized.get("fast", max(3, period // 2)))
            slow = int(normalized.get("slow", max(fast + 1, period)))
        return {
            "fast": max(2, fast),
            "slow": max(max(3, fast + 1), slow),
            "size": max(1, int(normalized.get("size", 100))),
        }

    if strategy == "macd":
        return {
            "fast": int(normalized.get("fast", 12)),
            "slow": int(normalized.get("slow", 26)),
            "signal": int(normalized.get("signal", 9)),
            "size": max(1, int(normalized.get("size", 100))),
        }

    if strategy == "bollinger":
        return {
            "period": int(normalized.get("period", 20)),
            "std_dev": float(normalized.get("std_dev", normalized.get("devfactor", 2.0))),
            "size": max(1, int(normalized.get("size", 100))),
        }

    # Fallback: use EMA to keep pipeline end-to-end instead of hard fail.
    return {"fast": 10, "slow": 30, "size": 100}


def _extract_alignment_metrics(
    backtest_nav: Any,
    paper_nav: Any,
    *,
    alignment_threshold: float = DEFAULT_ALIGNMENT_THRESHOLD,
    alignment_fail_threshold: float = DEFAULT_ALIGNMENT_FAIL_THRESHOLD,
) -> Dict[str, Any]:
    reconciler = Reconciler()
    if not isinstance(backtest_nav, pd.Series) or not isinstance(paper_nav, pd.Series):
        return {
            "status": "skip",
            "message": "NAV series missing for comparison",
            "details": {},
        }

    comparison = reconciler.compare_nav(
        backtest_nav.astype(float).rename("bt"),
        paper_nav.astype(float).rename("lv"),
    )
    cum_diff = comparison.get("cum_diff", pd.Series(dtype=float))
    aligned_bt = comparison.get("aligned_bt", pd.Series(dtype=float))
    aligned_lv = comparison.get("aligned_live", pd.Series(dtype=float))

    if cum_diff.empty or len(cum_diff) < MIN_ALIGNMENT_POINTS:
        return {
            "status": "warn",
            "message": "Alignment sample too small for stable statistics",
            "details": {
                "points": len(cum_diff),
                "max_abs_diff": _to_float_or_none(comparison.get("max_abs_diff", 0.0)),
                "threshold": alignment_threshold,
            },
        }

    returns = pd.concat([aligned_bt, aligned_lv], axis=1).pct_change().dropna()
    nav_corr = None
    if not returns.empty and returns.shape[1] >= 2:
        nav_corr = _to_float_or_none(returns.iloc[:, 0].corr(returns.iloc[:, 1]))

    drift_dates = reconciler.detect_drift(comparison, threshold=alignment_threshold)
    drift_max = _to_float_or_none(comparison.get("max_abs_diff", 0.0))
    drift_pct = drift_max * 100 if drift_max is not None else None
    passed = drift_max is not None and drift_max <= alignment_threshold
    status = "pass" if passed else (
        "fail" if drift_max is not None and drift_max > alignment_fail_threshold else "warn"
    )

    return {
        "status": status,
        "message": "Backtest/Paper alignment computed",
        "details": {
            "points": int(len(cum_diff)),
            "max_abs_diff": drift_max,
            "max_abs_diff_pct": drift_pct,
            "drift_points": len(drift_dates),
            "drift_threshold": alignment_threshold,
            "fail_threshold": alignment_fail_threshold,
            "nav_corr": nav_corr,
        },
    }


def run_preflight_checks(
    *,
    config: ConfigManager,
    strategy: str = "macd",
    symbols: Optional[Sequence[str]] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    source: Optional[str] = None,
    cache_dir: Optional[str] = None,
    cash: float = 200000.0,
    commission: float = 0.0001,
    slippage: float = 0.0005,
    params: Optional[Dict[str, Any]] = None,
    mode: str = "paper",
    run_backtest_smoke: bool = True,
    run_paper_smoke: bool = True,
    alignment_threshold: float = DEFAULT_ALIGNMENT_THRESHOLD,
    alignment_fail_threshold: float = DEFAULT_ALIGNMENT_FAIL_THRESHOLD,
) -> Dict[str, Any]:
    """Run the preflight pipeline and return a structured report."""
    checks: List[PreflightCheck] = []

    resolved_strategy, requested_strategy, alias_resolved = _resolve_strategy_name(strategy)
    requested_params = params or {}
    unified_params = _build_unified_strategy_params(resolved_strategy, requested_params)
    symbol_list = _to_list(symbols)
    symbols_norm = symbol_list if symbol_list else _default_symbol_list(config)
    source_name = source or config.data.provider
    cache_path = cache_dir or config.data.cache_dir

    dates = _default_window(days=90)
    start_date = start or dates["start"]
    end_date = end or dates["end"]

    # 1) Reuse existing health checks for baseline correctness
    base_checker = HealthChecker()
    base_checker.run_all_checks()
    for item in base_checker.checks:
        checks.append(
            PreflightCheck(
                name=item["name"],
                status=item["status"],
                message=item["message"],
                details=item["details"],
            )
        )

    # 2) Strategy registry and config sanity
    config_warnings = config.validate_all() if hasattr(config, "validate_all") else []
    checks.append(
        PreflightCheck(
            name="config_validation",
            status="pass" if not config_warnings else "warn",
            message="Config validation passed"
            if not config_warnings
            else "Config validation produced warnings",
            details={"warnings": config_warnings},
        )
    )

    checks.append(
        PreflightCheck(
            name="strategy_alias",
            status="pass" if resolved_strategy in STRATEGY_REGISTRY else "fail",
            message=(
                f"Strategy alias resolved: {requested_strategy} -> {resolved_strategy}"
                if alias_resolved else f"Strategy '{requested_strategy}' loaded directly"
            )
            if resolved_strategy in STRATEGY_REGISTRY
            else f"Strategy '{requested_strategy}' not found",
            details={"requested": requested_strategy, "resolved": resolved_strategy, "available_count": len(STRATEGY_REGISTRY)},
        )
    )
    if resolved_strategy not in STRATEGY_REGISTRY:
        checks.append(
            PreflightCheck(
                name="strategy_registry",
                status="fail",
                message=f"策略 '{requested_strategy}' 不在回测注册表内",
                details={"available_count": len(STRATEGY_REGISTRY)},
            )
        )
        strategy_not_found_analysis = {
            "requested_strategy": requested_strategy,
            "resolved_strategy": resolved_strategy,
            "alias_resolved": alias_resolved,
            "alignment_status": "fail",
            "drift": None,
            "drift_pct": None,
            "advice_level": "block",
            "parameter_guidance": ["策略别名映射失败，需确认策略在注册表中存在。"],
            "strategy_advice": ["策略别名映射失败，需确认策略在注册表中存在。"],
            "candidate_grid": [],
            "candidate_plan": {
                "status": "pause_before_market",
                "reason": "strategy_missing",
                "recommendation": "fix_strategy",
            },
            "strategy_advice_payload": {
                "advice_level": "block",
                "suggestions": ["策略别名映射失败，需确认策略在注册表中存在。"],
                "candidate_grid": [],
                "candidate_plan": {
                    "status": "pause_before_market",
                    "reason": "strategy_missing",
                    "recommendation": "fix_strategy",
                },
            },
        }
        return {
            "overall": "unhealthy",
            "checks": [c.__dict__ for c in checks],
            "summary": {
                "total": len(checks),
                "passed": len([c for c in checks if c.status == "pass"]),
                "warn": len([c for c in checks if c.status == "warn"]),
                "failed": 1,
                "skipped": len([c for c in checks if c.status == "skip"]),
            },
            "data_window": {"start": start_date, "end": end_date},
            "config": {
                "strategy": resolved_strategy,
                "requested_strategy": requested_strategy,
                "strategy_params_requested": requested_params,
                "strategy_params_unified_for_replay": unified_params,
                "symbols": symbols_norm,
                "source": source_name,
                "cache_dir": cache_path,
                "mode": mode,
                "alignment_threshold": alignment_threshold,
                "alignment_fail_threshold": alignment_fail_threshold,
                "alias_resolved": alias_resolved,
            },
            "backtest": {},
            "paper": {},
            "analysis": strategy_not_found_analysis,
        }

    # 3) Optional live mode gateway readiness checks
    if mode == "live":
        enabled = bool(config.live_trading.enabled)
        broker_cfg = getattr(config.live_trading, "broker", "paper")
        checks.append(
            PreflightCheck(
                name="live_config",
                status="pass" if enabled else "warn",
                message=(
                    "Live trading enabled and broker config loaded"
                    if enabled
                    else "Live trading disabled in config"
                ),
                details={
                    "enabled": enabled,
                    "broker": broker_cfg,
                    "account_id": getattr(config.live_trading, "account_id", ""),
                },
            )
        )
        if enabled:
            try:
                BrokerType(broker_cfg)
                checks.append(
                    PreflightCheck(
                        name="live_broker_enum",
                        status="pass",
                        message=f"Supported broker enum: {broker_cfg}",
                    )
                )
            except ValueError as exc:
                checks.append(
                    PreflightCheck(
                        name="live_broker_enum",
                        status="fail",
                        message=f"Unsupported live broker: {broker_cfg}",
                        details={"error": str(exc)},
                    )
                )
            if not getattr(config.live_trading, "account_id", ""):
                checks.append(
                    PreflightCheck(
                        name="live_account_id",
                        status="warn",
                        message="Live account_id is empty; real trading may fail auth",
                    )
                )

    # 4) Backtest smoke
    backtest_payload: Dict[str, Any] = {}
    if run_backtest_smoke:
        try:
            result = _safe_run_backtest(
                strategy=resolved_strategy,
                symbols=symbols_norm,
                start=start_date,
                end=end_date,
                source=source_name,
                cache_dir=cache_path,
                cash=cash,
                commission=commission,
                slippage=slippage,
                params=requested_params,
            )
            bt_nav = result.get("nav")
            bt_metrics = result.get("metrics", {})
            checks.append(
                PreflightCheck(
                    name="backtest_smoke",
                    status="pass",
                    message="Backtest smoke passed",
                    details={
                        "cum_return": _to_float_or_none(bt_metrics.get("cum_return")),
                        "trades": bt_metrics.get("trades", 0),
                        "len_nav": len(bt_nav) if isinstance(bt_nav, pd.Series) else None,
                    },
                )
            )
            backtest_payload = {"metrics": bt_metrics, "nav": bt_nav}
        except Exception as exc:
            checks.append(
                PreflightCheck(
                    name="backtest_smoke",
                    status="fail",
                    message="Backtest smoke test failed",
                    details={"error": str(exc)},
                )
            )
    else:
        checks.append(
            PreflightCheck(
                name="backtest_smoke",
                status="skip",
                message="Backtest smoke skipped",
            )
        )

    # 5) Paper-replay smoke + strategy behavior consistency
    paper_payload: Dict[str, Any] = {}
    if run_paper_smoke and mode in {"paper", "live"}:
        try:
            bt_metrics = backtest_payload.get("metrics", {})
            bt_nav = backtest_payload.get("nav")
            result = _safe_run_paper(
                strategy_name=resolved_strategy,
                params=unified_params,
                symbols=symbols_norm,
                start=start_date,
                end=end_date,
                source=source_name,
                cache_dir=cache_path,
                cash=cash,
                commission=commission,
                slippage=slippage,
                adj=getattr(config.data, "adj", None),
            )
            paper_nav = result.get("nav")
            paper_metrics = result.get("metrics", {})
            paper_trades = result.get("trades", [])
            checks.append(
                PreflightCheck(
                    name="paper_smoke",
                    status="pass",
                    message="Paper replay smoke passed",
                    details={
                        "total_return": paper_metrics.get("total_return"),
                        "sharpe_ratio": paper_metrics.get("sharpe_ratio"),
                        "trades": len(paper_trades),
                        "len_nav": len(paper_nav) if isinstance(paper_nav, pd.Series) else None,
                    },
                )
            )
            paper_payload = {"metrics": paper_metrics, "nav": paper_nav}
            paper_payload["trade_count"] = len(paper_trades)

            if bt_nav is not None and paper_nav is not None:
                alignment = _extract_alignment_metrics(
                    backtest_nav=bt_nav,
                    paper_nav=paper_nav,
                    alignment_threshold=alignment_threshold,
                    alignment_fail_threshold=alignment_fail_threshold,
                )
                bt_return = _to_float_or_none(bt_metrics.get("cum_return"))
                paper_return = _to_float_or_none(paper_metrics.get("total_return"))
                if paper_return is not None:
                    paper_return = paper_return / 100.0

                bt_trade_count = int(bt_metrics.get("trades", 0) or 0)
                paper_trade_count = len(paper_trades)
                checks.append(
                    PreflightCheck(
                        name="backtest_paper_alignment",
                        status=alignment["status"],
                        message=alignment["message"],
                        details={
                            "resolved_strategy": resolved_strategy,
                            "backtest_cum_return": bt_return,
                            "paper_return_decimal": paper_return,
                            "return_drift": (
                                paper_return - bt_return
                                if paper_return is not None and bt_return is not None
                                else None
                            ),
                            "trade_count_gap": paper_trade_count - bt_trade_count,
                            **alignment["details"],
                        },
                    )
                )
                advice = _build_strategy_advice(
                    strategy=resolved_strategy,
                    requested_params=requested_params,
                    unified_params=unified_params,
                    alignment=alignment,
                    backtest_metrics=bt_metrics,
                    paper_metrics=paper_metrics,
                    backtest_trades=bt_trade_count,
                    paper_trades=paper_trade_count,
                )
                analysis = {
                    "requested_strategy": requested_strategy,
                    "resolved_strategy": resolved_strategy,
                    "alias_resolved": alias_resolved,
                    "alignment_status": alignment["status"],
                    "drift": alignment["details"].get("max_abs_diff"),
                    "drift_pct": alignment["details"].get("max_abs_diff_pct"),
                    "parameter_guidance": advice.get("suggestions", []),
                    "advice_level": advice.get("advice_level", "info"),
                    "candidate_grid": advice.get("candidate_grid", []),
                    "candidate_plan": advice.get("candidate_plan", {}),
                }
                backtest_payload["analysis"] = analysis
                paper_payload["analysis"] = analysis
        except Exception as exc:
            checks.append(
                PreflightCheck(
                    name="paper_smoke",
                    status="fail",
                    message="Paper replay smoke failed",
                    details={"error": str(exc)},
                )
            )
    else:
        checks.append(
            PreflightCheck(
                name="paper_smoke",
                status="skip",
                message="Paper smoke skipped",
            )
        )

    failed = [c for c in checks if c.status == "fail"]
    overall = "healthy" if not failed else "unhealthy"

    final_analysis = backtest_payload.get("analysis") or paper_payload.get("analysis") or {}
    final_suggestions = final_analysis.get("parameter_guidance", [])
    if not isinstance(final_suggestions, list):
        final_suggestions = final_analysis.get("suggestions", [])
    if not isinstance(final_suggestions, list):
        final_suggestions = []

    return {
        "overall": overall,
        "checks": [c.__dict__ for c in checks],
        "summary": {
            "total": len(checks),
            "passed": len([c for c in checks if c.status == "pass"]),
            "warn": len([c for c in checks if c.status == "warn"]),
            "failed": len(failed),
            "skipped": len([c for c in checks if c.status == "skip"]),
        },
        "data_window": {"start": start_date, "end": end_date},
        "config": {
            "strategy": resolved_strategy,
            "requested_strategy": requested_strategy,
            "strategy_params_requested": requested_params,
            "strategy_params_unified_for_replay": unified_params,
            "symbols": symbols_norm,
            "source": source_name,
            "cache_dir": cache_path,
            "mode": mode,
            "alignment_threshold": alignment_threshold,
            "alignment_fail_threshold": alignment_fail_threshold,
            "alias_resolved": alias_resolved,
        },
        "backtest": backtest_payload,
        "paper": paper_payload,
        "analysis": {
            "requested_strategy": requested_strategy,
            "resolved_strategy": resolved_strategy,
            "alias_resolved": alias_resolved,
            "alignment_status": final_analysis.get("alignment_status"),
            "drift": final_analysis.get("drift"),
            "drift_pct": final_analysis.get("drift_pct"),
            "strategy_advice": final_suggestions,
            "parameter_guidance": final_analysis.get("parameter_guidance", []),
            "advice_level": final_analysis.get("advice_level", "info"),
            "candidate_grid": final_analysis.get("candidate_grid", []),
            "candidate_plan": final_analysis.get("candidate_plan", {}),
            "strategy_advice_payload": final_analysis,
        },
    }


def _print_report(report: Dict[str, Any]) -> None:
    """Print concise, human-readable report."""
    print("\n" + "=" * 70)
    print("上线预检报告")
    print("=" * 70)
    print(f"总体状态: {report['overall'].upper()}")
    print(f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(
        f"检查数: {report['summary']['total']} | "
        f"通过: {report['summary']['passed']} | "
        f"告警: {report['summary']['warn']} | "
        f"失败: {report['summary']['failed']} | "
        f"跳过: {report['summary']['skipped']}"
    )
    requested = report["config"].get("requested_strategy", report["config"]["strategy"])
    resolved = report["config"]["strategy"]
    print(f"策略: {requested} -> {resolved} (alias_resolved={report['config'].get('alias_resolved', False)})")
    print(f"标的: {', '.join(report['config']['symbols'])}")
    print(f"数据: {report['data_window']['start']} -> {report['data_window']['end']}")
    print()

    for item in report["checks"]:
        status = item["status"].upper()
        icon = {"pass": "✓", "warn": "⚠", "fail": "✗", "skip": "→"}.get(item["status"], "?")
        print(f"{icon} [{status}] {item['name']}")
        if item["message"]:
            print(f"    {item['message']}")
        for key, value in item.get("details", {}).items():
            if value is None:
                continue
            print(f"    {key}: {value}")

    analysis = report.get("analysis", {})
    analysis_advice = analysis.get("strategy_advice", [])
    if not isinstance(analysis_advice, list):
        analysis_advice = []
    if not analysis_advice:
        analysis_advice = analysis.get("parameter_guidance", [])
        if not isinstance(analysis_advice, list):
            analysis_advice = analysis.get("strategy_advice_payload", {}).get("suggestions", [])
            if not isinstance(analysis_advice, list):
                analysis_advice = []

    advice_level = analysis.get("advice_level", "info")
    candidate_plan = analysis.get("candidate_plan") or analysis.get("strategy_advice_payload", {}).get("candidate_plan", {})
    candidate_grid = analysis.get("candidate_grid")
    if isinstance(candidate_plan, dict) and candidate_plan.get("candidate_grid"):
        candidate_grid = candidate_plan["candidate_grid"]

    print(f"\n策略优化建议（{advice_level}）")
    if analysis_advice:
        for suggestion in analysis_advice:
            print(f"  - {suggestion}")

    if isinstance(candidate_plan, dict):
        print("\n参数复检计划")
        if candidate_plan.get("status"):
            print(f"  - status: {candidate_plan.get('status')}")
        if candidate_plan.get("reason"):
            print(f"  - reason: {candidate_plan.get('reason')}")
        if candidate_plan.get("recommendation"):
            print(f"  - recommendation: {candidate_plan.get('recommendation')}")
        if candidate_plan.get("notes"):
            notes = candidate_plan["notes"]
            if not isinstance(notes, list):
                notes = [str(notes)]
            for note in notes:
                print(f"  - note: {note}")

    if isinstance(candidate_grid, list) and candidate_grid:
        print("\n参数候选网格")
        for idx, item in enumerate(candidate_grid, 1):
            print(f"  - {idx}. {item}")

    if report["overall"] != "healthy":
        print("\n建议: 请修复失败项后再启动服务。")
    print("=" * 70)


def main() -> None:
    parser = argparse.ArgumentParser(description="生产上线预检")
    parser.add_argument("--config", default=None, help="配置文件路径")
    parser.add_argument("--strategy", default="macd", help="回测/策略分析策略名")
    parser.add_argument("--symbols", nargs="+", default=None, help="标的代码，多个用空格分隔")
    parser.add_argument("--source", default=None, help="数据源: akshare / yfinance / tushare / qlib")
    parser.add_argument("--start", default=None, help="回测窗口开始时间 YYYY-MM-DD")
    parser.add_argument("--end", default=None, help="回测窗口结束时间 YYYY-MM-DD")
    parser.add_argument("--cache-dir", default=None, help="数据缓存目录")
    parser.add_argument("--mode", choices=["backtest", "paper", "live"], default="paper")
    parser.add_argument("--skip-backtest", action="store_true", help="跳过回测烟雾测试")
    parser.add_argument("--skip-paper", action="store_true", help="跳过实盘回放烟雾测试")
    parser.add_argument(
        "--alignment-threshold",
        type=float,
        default=DEFAULT_ALIGNMENT_THRESHOLD,
        help="回测与回放 NAV 漂移告警阈值（默认 0.03）",
    )
    parser.add_argument(
        "--alignment-fail-threshold",
        type=float,
        default=DEFAULT_ALIGNMENT_FAIL_THRESHOLD,
        help="回测与回放 NAV 漂移硬失败阈值（默认 0.10）",
    )
    parser.add_argument("--params", default=None, help="策略参数 JSON")
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    parser.add_argument("--exit-code", action="store_true", help="以非0退出码表示预检失败")
    args = parser.parse_args()

    if args.config:
        config_manager = ConfigManager.load_from_file(args.config)
    else:
        config_manager = ConfigManager()

    try:
        strategy_params = json.loads(args.params) if args.params else None
    except Exception as exc:
        logger.error("解析 --params 失败: %s", exc)
        strategy_params = None
    if strategy_params is None:
        strategy_params = {}

    report = run_preflight_checks(
        config=config_manager,
        strategy=args.strategy,
        symbols=args.symbols,
        start=args.start,
        end=args.end,
        source=args.source,
        cache_dir=args.cache_dir,
        mode=args.mode,
        alignment_threshold=args.alignment_threshold,
        alignment_fail_threshold=args.alignment_fail_threshold,
        params=strategy_params,
        run_backtest_smoke=not args.skip_backtest,
        run_paper_smoke=not args.skip_paper,
    )

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    else:
        _print_report(report)

    if args.exit_code:
        sys.exit(0 if report["overall"] == "healthy" else 1)


if __name__ == "__main__":
    main()
