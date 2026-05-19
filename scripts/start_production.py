#!/usr/bin/env python3
"""
生产环境启动脚本

提供完整的生产环境启动流程，包括：
- 配置加载和验证
- 目录初始化
- 日志配置
- 健康检查
- 优雅关闭处理

用法:
    python scripts/start_production.py
    python scripts/start_production.py --config config.yaml
    python scripts/start_production.py --mode backtest
"""
from __future__ import annotations

import argparse
import signal
import sys
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.logger import configure_logging, get_logger
from src.core.config import ConfigManager, get_config
from src.core.defaults import ensure_directories, PATHS
from src.backtest.admission_gates import (
    DEFAULT_STRATEGY_GATE_ROOT,
    MissingStrategyGateStage,
    build_strategy_gate_summary,
    load_strategy_gate,
    promote_strategy_gate,
    require_strategy_stage,
    strategy_gate_path,
)
from scripts.health_check import HealthChecker
from scripts.preflight_check import run_preflight_checks
from scripts.preflight_experiment_platform import (
    build_experiment_specs_from_report,
    run_experiment_batch,
)

logger = None


def _resolve_strategy_gate_root(path: Optional[str]) -> str:
    normalized = str(path or "").strip()
    if not normalized:
        normalized = DEFAULT_STRATEGY_GATE_ROOT
    return os.path.abspath(normalized)


def _resolve_strategy_gate_params(
    config: Any,
    *,
    explicit_params: Optional[Dict[str, Any]] = None,
    report: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if isinstance(report, dict):
        config_payload = report.get("config", {})
        if isinstance(config_payload, dict):
            requested = config_payload.get("strategy_params_requested")
            if isinstance(requested, dict):
                return dict(requested)

    if isinstance(explicit_params, dict) and explicit_params:
        return dict(explicit_params)

    strategy_cfg = getattr(config, "strategy", None)
    configured = getattr(strategy_cfg, "params", {}) if strategy_cfg is not None else {}
    return dict(configured) if isinstance(configured, dict) else {}


def _resolve_runtime_strategy(config: Any) -> str:
    strategy_cfg = getattr(config, "strategy", None)
    token = getattr(strategy_cfg, "name", None)
    normalized = str(token or "macd").strip().lower()
    return normalized or "macd"


def _paper_smoke_passed(report: Dict[str, Any]) -> bool:
    checks = report.get("checks", []) if isinstance(report, dict) else []
    for item in checks:
        if isinstance(item, dict) and item.get("name") == "paper_smoke":
            return item.get("status") == "pass"
    return False


def _strategy_gate_summary(
    strategy_name: str,
    params: Dict[str, Any],
    gate_root: str,
    payload: Optional[Dict[str, Any]],
    *,
    required_stage: Optional[str] = None,
) -> Dict[str, Any]:
    summary = build_strategy_gate_summary(payload)
    summary.update(
        {
            "strategy": strategy_name,
            "gate_root": gate_root,
            "path": strategy_gate_path(strategy_name, params=params, gate_root=gate_root),
        }
    )
    if required_stage:
        summary["required_stage"] = required_stage
    return summary


def _build_strategy_gate_block_decision(
    *,
    strategy_name: str,
    params: Dict[str, Any],
    gate_root: str,
    required_stage: str,
    current_payload: Optional[Dict[str, Any]],
    reason: str,
) -> Dict[str, Any]:
    return {
        "decision_state": "block",
        "decision_reasons": [reason],
        "required_overrides": [],
        "recommended_replay": None,
        "next_actions": [
            f"请先完成策略门禁阶段：{required_stage}",
            "使用 unified_backtest_framework.py baseline/admission 和 paper/live preflight 逐步推进阶段。",
        ],
        "summary": {
            "overall": "unhealthy",
            "advice_level": "block",
            "warn_count": 0,
            "failed_count": 1,
            "platform_ran": False,
            "sweep_ran": False,
            "selected_best_source": None,
        },
        "strategy_gate": _strategy_gate_summary(
            strategy_name,
            params,
            gate_root,
            current_payload,
            required_stage=required_stage,
        ),
    }


def _require_live_launch_gate(config: Any, args: argparse.Namespace) -> Dict[str, Any]:
    strategy_name = _resolve_runtime_strategy(config)
    params = _resolve_strategy_gate_params(config)
    gate_root = _resolve_strategy_gate_root(getattr(args, "preflight_gate_root", None))
    return require_strategy_stage(
        strategy_name,
        "live_candidate",
        params=params,
        gate_root=gate_root,
    )


def _mark_live_production_gate(config: Any, args: argparse.Namespace) -> Dict[str, Any]:
    strategy_name = _resolve_runtime_strategy(config)
    params = _resolve_strategy_gate_params(config)
    gate_root = _resolve_strategy_gate_root(getattr(args, "preflight_gate_root", None))
    return promote_strategy_gate(
        strategy_name,
        "production",
        params=params,
        gate_root=gate_root,
        source="startup.live",
        details={
            "mode": "live",
            "config_path": args.config,
        },
    )


def _extract_replay_params_from_decision(decision: object) -> Dict[str, Any]:
    """Extract recommended replay params from a release decision payload."""
    if not isinstance(decision, dict):
        return {}
    if "release_decision" in decision:
        nested = decision.get("release_decision")
        if isinstance(nested, dict):
            decision = nested
    recommended = decision.get("recommended_replay")
    if not isinstance(recommended, dict):
        return {}
    params = recommended.get("params")
    if isinstance(params, dict):
        return params
    return {}


def _load_replay_params_from_decision_file(path: Optional[str]) -> Dict[str, Any]:
    """Load preflight params from a previous decision JSON file."""
    normalized = _coerce_preflight_result_path(path)
    if not normalized:
        return {}

    try:
        with open(normalized, "r", encoding="utf-8") as fp:
            payload = json.load(fp)
    except FileNotFoundError:
        logger.debug(f"preflight seed decision file not found: {normalized}")
        return {}
    except Exception as exc:
        logger.warning(f"Failed to load preflight seed decision file {normalized}: {exc}")
        return {}

    params = _extract_replay_params_from_decision(payload)
    if not params:
        logger.info(f"No recommended_replay.params found in seed file: {normalized}")
        return {}

    logger.info(f"Loaded recommended params from preflight seed file: {normalized} (keys={sorted(params.keys())})")
    return params


def _to_float(value: object) -> Optional[float]:
    """Safely cast value to float."""
    try:
        if value is None:
            return None
        converted = float(value)
    except (TypeError, ValueError):
        return None
    if converted != converted:
        return None
    return converted


def _normalize_candidate_grid(analysis: dict, limit: int) -> list:
    """Normalize preflight candidate grid output."""
    candidates = analysis.get("candidate_grid") or analysis.get("strategy_advice_payload", {}).get("candidate_grid", [])
    if not isinstance(candidates, list):
        return []
    normalized = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        normalized.append(item)
    if not normalized:
        return []
    try:
        candidate_limit = int(limit)
    except (TypeError, ValueError):
        candidate_limit = len(normalized)
    if candidate_limit <= 0:
        candidate_limit = len(normalized)
    return normalized[:candidate_limit] if normalized else []


def _score_candidate_overview(
    level: str,
    overall: str,
    drift: Optional[float],
) -> tuple:
    """Build a stable ranking key for candidate comparison."""
    level_weight = {"info": 0, "warn": 1, "block": 2}
    overall_weight = 0 if overall == "healthy" else 1
    drift_rank = abs(drift) if drift is not None else 1e9
    return (overall_weight, level_weight.get(str(level or "info"), 3), drift_rank)


def _build_release_replay_payload(
    preflight_strategy: str,
    preflight_mode: str,
    args: argparse.Namespace,
    best_item: Dict[str, Any],
    source: str,
) -> Dict[str, Any]:
    """Build a stable replay payload from the best experiment candidate."""
    params = best_item.get("requested_params")
    if not isinstance(params, dict):
        return {}
    payload = _build_preflight_candidate_payload(
        preflight_strategy=preflight_strategy,
        preflight_mode=preflight_mode,
        symbols=args.preflight_symbols,
        args=args,
        params=params,
    )
    payload.update(
        {
            "selection_source": source,
            "experiment_id": best_item.get("experiment_id"),
            "label": best_item.get("label"),
            "status": best_item.get("overall"),
            "advice_level": best_item.get("advice_level"),
            "drift": best_item.get("drift"),
            "drift_pct": best_item.get("drift_pct"),
            "elapsed_seconds": best_item.get("elapsed_seconds"),
            "selection_ts": datetime.now().isoformat(),
        }
    )
    return payload


def _build_release_decision(
    report: Dict[str, Any],
    preflight_mode: str,
    preflight_strategy: str,
    args: argparse.Namespace,
    *,
    platform_run: Optional[Dict[str, Any]] = None,
    sweep_run: Optional[Dict[str, Any]] = None,
    selected_best: Optional[Dict[str, Any]] = None,
    selected_best_source: Optional[str] = None,
) -> Dict[str, Any]:
    """Build structured production release decision object."""
    analysis = report.get("analysis", {})
    if not isinstance(analysis, dict):
        analysis = {}
    summary = report.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}

    overall = str(report.get("overall", "unhealthy")).lower()
    advice_level = str(analysis.get("advice_level", "info")).lower()
    warn_count = int(summary.get("warn", 0) or 0)
    failed_count = int(summary.get("failed", 0) or 0)

    decision_reasons: List[str] = []
    required_overrides: List[str] = []
    next_actions: List[str] = []

    if failed_count > 0:
        decision_state = "block"
        decision_reasons.append(f"预检失败项存在: failed={failed_count}")
    elif overall != "healthy":
        decision_state = "block"
        decision_reasons.append(f"预检整体状态异常: overall={overall}")
    else:
        decision_state = "approve"
        decision_reasons.append("预检整体健康通过")

    if preflight_mode == "live":
        if advice_level == "block":
            decision_reasons.append("建议级别为 block，存在实盘放量高风险")
            if not args.preflight_allow_block:
                decision_state = "block"
                required_overrides.append("--preflight-allow-block")
                next_actions.append("建议修复失败项后再启动，或明确临时放行参数")
            elif decision_state == "approve":
                decision_state = "review"
        elif advice_level == "warn":
            decision_reasons.append("建议级别为 warn，建议保守放量")
            if not args.preflight_allow_warn:
                decision_state = "block"
                required_overrides.append("--preflight-allow-warn")
                next_actions.append("建议补齐告警项后再启动")
            elif decision_state == "approve":
                decision_state = "review"
        elif warn_count and decision_state == "approve":
            decision_reasons.append(f"存在告警项: warn={warn_count}")
            decision_state = "review"
    else:
        if advice_level in {"warn", "block"}:
            decision_state = "review" if decision_state == "approve" else decision_state
            decision_reasons.append(f"建议级别 {advice_level}，建议人工复核")
        if warn_count:
            decision_reasons.append(f"存在告警项: warn={warn_count}")

    if platform_run:
        run_id = platform_run.get("platform_run_id")
        if isinstance(run_id, str) and run_id:
            next_actions.append(f"实验平台 run_id={run_id}，请保留用于溯源")
    if sweep_run:
        if sweep_run.get("status") == "completed":
            next_actions.append("候选复检已完成，可用于参数复用")
        if sweep_run.get("best"):
            next_actions.append("候选复检 best 已写入 report.recommended_replay")

    recommended_replay = {}
    if isinstance(selected_best, dict) and selected_best.get("requested_params"):
        recommended_replay = _build_release_replay_payload(
            preflight_strategy=preflight_strategy,
            preflight_mode=preflight_mode,
            args=args,
            best_item=selected_best,
            source=selected_best_source or "unknown",
        )
        decision_reasons.append(
            f"已选出最优候选（来源={selected_best_source or 'unknown'}），建议按 recommended_replay 重放"
        )

    if decision_state == "approve":
        next_actions.append("可进入正式启动流程")
    elif decision_state == "review":
        next_actions.append("建议先核验参数复用窗口并复跑一次全流程 smoke")
    else:
        next_actions.append("请先修复失败项或使用 overrides 进行受控继续")

    seen_required = []
    for item in required_overrides:
        if item not in seen_required:
            seen_required.append(item)

    seen_actions: List[str] = []
    for item in next_actions:
        if item not in seen_actions:
            seen_actions.append(item)

    return {
        "decision_state": decision_state,
        "decision_reasons": decision_reasons,
        "required_overrides": seen_required,
        "recommended_replay": recommended_replay or None,
        "next_actions": seen_actions,
        "summary": {
            "overall": overall,
            "advice_level": advice_level,
            "warn_count": warn_count,
            "failed_count": failed_count,
            "platform_ran": bool(platform_run),
            "sweep_ran": bool(sweep_run),
            "selected_best_source": selected_best_source,
        },
    }


def _coerce_preflight_result_path(path: Optional[str]) -> Optional[str]:
    if path is None:
        return None
    normalized = str(path).strip()
    if not normalized:
        return None
    return normalized


def _coerce_preflight_auto_rounds(value: Optional[int]) -> int:
    try:
        rounds = int(value)
    except (TypeError, ValueError):
        return 1
    if rounds < 1:
        return 1
    return rounds


def _has_recommended_replay_params(decision: Dict[str, Any]) -> bool:
    return bool(_extract_replay_params_from_decision(decision))


def _persist_preflight_decision_files(
    release_decision: Dict[str, Any],
    decision_path: Optional[str],
    seed_path: Optional[str],
    *,
    logger_obj=None,
) -> bool:
    """Persist preflight decision to snapshot files.

    Returns False only when the primary decision file fails to persist.
    """
    logger_obj = logger_obj or logger
    if decision_path:
        try:
            target = Path(decision_path)
            if target.parent:
                target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("w", encoding="utf-8") as fp:
                json.dump(release_decision, fp, ensure_ascii=False, indent=2, default=str)
            if logger_obj:
                logger_obj.info(f"release_decision saved: {decision_path}")
        except Exception as exc:
            if logger_obj:
                logger_obj.error(f"Failed to save decision file: {exc}")
            return False

    if seed_path and seed_path != decision_path:
        try:
            target = Path(seed_path)
            if target.parent:
                target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("w", encoding="utf-8") as fp:
                json.dump(release_decision, fp, ensure_ascii=False, indent=2, default=str)
            if logger_obj:
                logger_obj.info(f"preflight decision seed updated: {seed_path}")
        except Exception as exc:
            if logger_obj:
                logger_obj.error(f"Failed to save preflight seed file: {exc}")

    return True


def _run_preflight_decision_only_cycles(
    config: Any,
    args: argparse.Namespace,
) -> Tuple[bool, Dict[str, Any], int]:
    """Run preflight in decision-only mode with optional auto replay cycles."""
    max_rounds = _coerce_preflight_auto_rounds(getattr(args, "preflight_auto_rounds", 1))
    auto_regression = bool(getattr(args, "preflight_auto_regression", False))
    if not auto_regression:
        max_rounds = 1

    decision_path = _coerce_preflight_result_path(args.preflight_decision_file)
    seed_path = _coerce_preflight_result_path(args.preflight_decision_seed_file)

    original_preflight_params = getattr(args, "preflight_params", None)
    final_passed = False
    final_decision: Dict[str, Any] = {}
    final_round = 0

    for current_round in range(1, max_rounds + 1):
        if logger:
            logger.info(f"Preflight decision round {current_round}/{max_rounds}")

        if current_round > 1:
            args.preflight_params = None

        passed, release_decision = _run_preflight_if_requested(config, args)
        final_round = current_round
        final_passed = passed
        final_decision = release_decision

        if not _persist_preflight_decision_files(
            release_decision=release_decision,
            decision_path=decision_path,
            seed_path=seed_path,
            logger_obj=logger,
        ):
            return False, release_decision, current_round

        decision_state = str(release_decision.get("decision_state", "unknown")).lower()
        if (
            not auto_regression
            or decision_state != "review"
            or not _has_recommended_replay_params(release_decision)
            or current_round >= max_rounds
        ):
            break

        if logger:
            logger.info(f"Decision round {current_round} is review and has recommended replay. Starting auto round {current_round + 1}.")
        args.preflight_params = None

    args.preflight_params = original_preflight_params
    return final_passed, final_decision, final_round


def _build_preflight_candidate_payload(
    preflight_strategy: str,
    preflight_mode: str,
    symbols,
    args: argparse.Namespace,
    params,
) -> dict:
    """Build machine- and human-friendly replay payload for a candidate."""
    return {
        "strategy": preflight_strategy,
        "mode": preflight_mode,
        "symbols": list(symbols) if isinstance(symbols, (list, tuple)) else symbols,
        "start": args.preflight_start,
        "end": args.preflight_end,
        "source": args.preflight_source,
        "cache_dir": args.preflight_cache_dir,
        "alignment_threshold": args.preflight_alignment_threshold,
        "alignment_fail_threshold": args.preflight_alignment_fail_threshold,
        "skip_backtest": bool(args.preflight_skip_backtest),
        "skip_paper": bool(args.preflight_skip_paper),
        "params": params,
    }


def _run_preflight_candidate_sweep(
    config,
    preflight_strategy,
    symbols,
    preflight_report,
    args,
    preflight_mode: str,
    config_cash: float,
    config_commission: float,
    config_slippage: float,
) -> dict:
    """Run quick paper-replay consistency sweeps for candidate parameters."""
    analysis = preflight_report if isinstance(preflight_report, dict) else None
    if analysis is None:
        return {"status": "skip", "reason": "no preflight result"}

    candidate_plan = analysis.get("analysis", {})
    candidate_grid = _normalize_candidate_grid(candidate_plan, args.preflight_sweep_limit)
    if not candidate_grid:
        return {"status": "skip", "reason": "no candidate grid"}

    try:
        candidate_limit = int(args.preflight_sweep_limit)
    except (TypeError, ValueError):
        candidate_limit = 3
    candidate_limit = max(1, min(len(candidate_grid), candidate_limit))
    candidates = candidate_grid[:candidate_limit]

    logger.info(f"Starting preflight candidate sweep: candidates={candidate_limit}")
    results = []
    best = None
    best_key = (1, 3, float("inf"))

    for idx, candidate in enumerate(candidates, 1):
        logger.info(f"[{idx}/{candidate_limit}] sweep candidate={candidate}")
        try:
            candidate_report = run_preflight_checks(
                config=config,
                strategy=preflight_strategy,
                symbols=symbols,
                start=args.preflight_start,
                end=args.preflight_end,
                source=args.preflight_source or None,
                cache_dir=args.preflight_cache_dir,
                mode=preflight_mode,
                cash=float(config_cash),
                commission=float(config_commission),
                slippage=float(config_slippage),
                params=candidate,
                run_backtest_smoke=not args.preflight_skip_backtest,
                run_paper_smoke=not args.preflight_skip_paper,
                alignment_threshold=args.preflight_alignment_threshold,
                alignment_fail_threshold=args.preflight_alignment_fail_threshold,
            )
            candidate_analysis = candidate_report.get("analysis", {})
            level = str(candidate_analysis.get("advice_level", "info")).lower()
            overall = str(candidate_report.get("overall", "unhealthy")).lower()
            drift = _to_float(candidate_analysis.get("drift"))
            key = _score_candidate_overview(level=level, overall=overall, drift=drift)
            result_item = {
                "candidate": candidate,
                "overall": overall,
                "advice_level": level,
                "drift": drift,
                "drift_pct": candidate_analysis.get("drift_pct"),
                "strategy_advice": candidate_analysis.get("strategy_advice", []),
                "candidate_plan": candidate_analysis.get("candidate_plan", {}),
            }
            results.append(result_item)
            if key < best_key:
                best_key = key
                best = result_item
                best["index"] = idx
        except Exception as exc:
            logger.warning(f"candidate sweep failed: {exc}")
            results.append({"candidate": candidate, "overall": "error", "reason": str(exc)})

    best_payload = None
    if best:
        best_payload = _build_preflight_candidate_payload(
            preflight_strategy=preflight_strategy,
            preflight_mode=preflight_mode,
            symbols=symbols,
            args=args,
            params=best.get("candidate"),
        )

    return {
        "status": "completed",
        "requested_limit": candidate_limit,
        "executed": len(results),
        "results": results,
        "best": best or {},
        "recommended_replay": best_payload,
    }


def setup_signal_handlers():
    """设置信号处理器，实现优雅关闭"""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    if hasattr(signal, 'SIGHUP'):
        signal.signal(signal.SIGHUP, signal_handler)


def load_configuration(config_path: Optional[str] = None) -> ConfigManager:
    """加载配置"""
    if config_path and os.path.exists(config_path):
        logger.info(f"Loading configuration from {config_path}")
        return ConfigManager.load_from_file(config_path)
    else:
        logger.info("Using default configuration")
        return ConfigManager()


def initialize_directories():
    """初始化必要目录"""
    logger.info("Initializing directories...")
    ensure_directories()
    
    for name, path in PATHS.items():
        if name not in ["database", "config"]:
            logger.debug(f"  {name}: {path}")


def run_health_check() -> bool:
    """运行健康检查"""
    logger.info("Running health checks...")
    checker = HealthChecker()
    checker.run_all_checks()
    
    if checker.overall_status == "healthy":
        logger.info("✓ All health checks passed")
        return True
    else:
        logger.warning("✗ Some health checks failed")
        failed_checks = [c for c in checker.checks if c["status"] == "fail"]
        for check in failed_checks:
            logger.warning(f"  Failed: {check['name']} - {check['message']}")
        return False


def start_backtest_mode(config: ConfigManager):
    """启动回测模式"""
    logger.info("Starting in BACKTEST mode...")
    # 这里可以启动回测服务或CLI
    logger.info("Backtest mode ready. Use CLI commands to run backtests.")


def start_paper_trading_mode(config: ConfigManager):
    """启动模拟交易模式"""
    logger.info("Starting in PAPER TRADING mode...")
    # 这里可以启动模拟交易服务
    logger.info("Paper trading mode ready.")


def start_live_trading_mode(config: ConfigManager):
    """启动实盘交易模式"""
    logger.warning("Starting in LIVE TRADING mode...")
    logger.warning("⚠️  WARNING: This will execute real trades!")
    
    # 确认实盘模式
    if not os.getenv("CONFIRM_LIVE_TRADING"):
        logger.error("LIVE TRADING mode requires CONFIRM_LIVE_TRADING environment variable")
        sys.exit(1)
    
    # 这里可以启动实盘交易服务
    logger.info("Live trading mode ready.")


def _run_preflight_if_requested(
    config: ConfigManager,
    args: argparse.Namespace,
) -> Tuple[bool, Dict[str, Any]]:
    """Run launch preflight checks if enabled."""
    if not args.preflight:
        return True, {
            "decision_state": "approve",
            "decision_reasons": ["未启用预检"],
            "required_overrides": [],
            "recommended_replay": None,
            "next_actions": ["可直接启动服务"],
            "summary": {"overall": "unknown", "advice_level": "info", "warn_count": 0, "failed_count": 0, "platform_ran": False, "sweep_ran": False, "selected_best_source": None},
        }

    strategy_default = getattr(getattr(config, "strategy", None), "name", None) or "macd"
    if strategy_default in {"", "default", None}:
        strategy_default = "macd"
    preflight_strategy = args.preflight_strategy or strategy_default
    preflight_mode = args.preflight_mode or args.mode
    preflight_params = {}

    if args.preflight_params:
        try:
            parsed = json.loads(args.preflight_params)
            if not isinstance(parsed, dict):
                logger.error("--preflight-params must be a JSON object.")
                return (
                    False,
                    {
                        "decision_state": "block",
                        "decision_reasons": ["--preflight-params 需要 JSON 对象"],
                        "required_overrides": [],
                        "recommended_replay": None,
                        "next_actions": ["请修正 --preflight-params 后重试"],
                        "summary": {"overall": "unhealthy", "advice_level": "block", "warn_count": 0, "failed_count": 1, "platform_ran": False, "sweep_ran": False, "selected_best_source": None},
                    },
                )
            preflight_params = parsed
        except Exception as exc:
            logger.error(f"Failed to parse --preflight-params: {exc}")
            return (
                False,
                {
                    "decision_state": "block",
                    "decision_reasons": [f"解析 --preflight-params 失败: {exc}"],
                    "required_overrides": [],
                    "recommended_replay": None,
                    "next_actions": ["请修正 --preflight-params 为合法 JSON 后重试"],
                    "summary": {"overall": "unhealthy", "advice_level": "block", "warn_count": 0, "failed_count": 1, "platform_ran": False, "sweep_ran": False, "selected_best_source": None},
                },
            )
    else:
        preflight_params = _load_replay_params_from_decision_file(
            getattr(args, "preflight_decision_seed_file", None)
        )

    gate_root = _resolve_strategy_gate_root(getattr(args, "preflight_gate_root", None))
    effective_gate_params = _resolve_strategy_gate_params(
        config,
        explicit_params=preflight_params,
    )
    required_stage = None
    current_gate = load_strategy_gate(
        preflight_strategy,
        params=effective_gate_params,
        gate_root=gate_root,
    )
    if preflight_mode == "live":
        required_stage = "paper_validated" if args.preflight_skip_paper else "admission_passed"
        try:
            require_strategy_stage(
                preflight_strategy,
                required_stage,
                params=effective_gate_params,
                gate_root=gate_root,
            )
        except MissingStrategyGateStage as exc:
            return False, _build_strategy_gate_block_decision(
                strategy_name=preflight_strategy,
                params=effective_gate_params,
                gate_root=gate_root,
                required_stage=required_stage,
                current_payload=current_gate,
                reason=f"实盘预检门禁未通过：{exc}",
            )

    report = run_preflight_checks(
        config=config,
        strategy=preflight_strategy,
        symbols=args.preflight_symbols,
        start=args.preflight_start,
        end=args.preflight_end,
        source=args.preflight_source or None,
        cache_dir=args.preflight_cache_dir,
        mode=preflight_mode,
        cash=float(config.backtest.initial_cash),
        commission=float(config.backtest.commission),
        slippage=float(config.backtest.slippage),
        run_backtest_smoke=not args.preflight_skip_backtest,
        run_paper_smoke=not args.preflight_skip_paper,
        alignment_threshold=args.preflight_alignment_threshold,
        alignment_fail_threshold=args.preflight_alignment_fail_threshold,
        params=preflight_params,
    )

    sweep_report: dict = {}
    platform_report: dict = {}
    selected_best: dict = {}
    selected_best_source = None
    platform_mode = "paper" if preflight_mode == "live" else preflight_mode

    if getattr(args, "preflight_platform_run", False):
        logger.info("preflight platform run enabled, building experiment specs from report")
        specs = build_experiment_specs_from_report(
            report=report,
            strategy=preflight_strategy,
            mode=platform_mode,
            include_base=True,
            max_candidates=max(int(args.preflight_platform_limit), 1),
        )
        if specs:
            platform_report = run_experiment_batch(
                config=config,
                preflight_strategy=preflight_strategy,
                specs=specs,
                args=args,
                logger=logger,
            )
        else:
            platform_report = {"status": "skip", "reason": "no_experiment_specs"}
        report["preflight_platform"] = platform_report
        best_plan = platform_report.get("best") if isinstance(platform_report, dict) else None
        if isinstance(best_plan, dict) and isinstance(best_plan.get("requested_params"), dict):
            selected_best = best_plan
            selected_best_source = "preflight_platform"
    elif getattr(args, "preflight_sweep", False):
        logger.info("legacy preflight sweep enabled; platform run not enabled")
        sweep_report = _run_preflight_candidate_sweep(
            config=config,
            preflight_strategy=preflight_strategy,
            symbols=args.preflight_symbols,
            preflight_report=report,
            args=args,
            preflight_mode="paper" if preflight_mode == "live" else preflight_mode,
            config_cash=float(config.backtest.initial_cash),
            config_commission=float(config.backtest.commission),
            config_slippage=float(config.backtest.slippage),
        )
        report["preflight_sweep"] = sweep_report
        best_plan = sweep_report.get("best") if isinstance(sweep_report, dict) else None
        if isinstance(best_plan, dict) and isinstance(best_plan.get("candidate"), dict):
            selected_best = {"requested_params": best_plan.get("candidate"), "overall": best_plan.get("overall"), "advice_level": best_plan.get("advice_level"), "drift": best_plan.get("drift"), "drift_pct": best_plan.get("drift_pct"), "experiment_id": "legacy_sweep_best"}
            selected_best_source = "preflight_sweep"

    if getattr(args, "preflight_use_best", False):
        best_candidate = selected_best.get("requested_params") if selected_best else None
        if isinstance(best_candidate, dict):
            logger.info(f"Applying best candidate from {selected_best_source or 'preflight experiments'} for rerun.")
            try:
                rerun_best = run_preflight_checks(
                    config=config,
                    strategy=preflight_strategy,
                    symbols=args.preflight_symbols,
                    start=args.preflight_start,
                    end=args.preflight_end,
                    source=args.preflight_source or None,
                    cache_dir=args.preflight_cache_dir,
                    mode=preflight_mode,
                    cash=float(config.backtest.initial_cash),
                    commission=float(config.backtest.commission),
                    slippage=float(config.backtest.slippage),
                    run_backtest_smoke=not args.preflight_skip_backtest,
                    run_paper_smoke=not args.preflight_skip_paper,
                    alignment_threshold=args.preflight_alignment_threshold,
                    alignment_fail_threshold=args.preflight_alignment_fail_threshold,
                    params=best_candidate,
                )
                rerun_best["preflight_selected_from_experiment"] = {
                    "source": selected_best_source,
                    "requested_params": best_candidate,
                    "selection_ts": datetime.now().isoformat(),
                }
                report = rerun_best
            except Exception as exc:
                logger.warning(f"Failed to rerun with best candidate: {exc}")
                report["preflight_selected_from_experiment_failed"] = str(exc)
        else:
            logger.warning("preflight_use_best enabled but no valid best candidate from experiments.")

    analysis = report.get("analysis", {})
    advice_level = analysis.get("advice_level", "info")
    candidate_plan = analysis.get("candidate_plan") or analysis.get("strategy_advice_payload", {}).get("candidate_plan", {})
    candidate_grid = analysis.get("candidate_grid") or analysis.get("strategy_advice_payload", {}).get("candidate_grid", [])
    strategy_advice = analysis.get("strategy_advice", [])
    if not isinstance(strategy_advice, list):
        strategy_advice = analysis.get("strategy_advice_payload", {}).get("suggestions", [])
        if not isinstance(strategy_advice, list):
            strategy_advice = []

    release_decision = _build_release_decision(
        report=report,
        preflight_mode=preflight_mode,
        preflight_strategy=preflight_strategy,
        args=args,
        platform_run=platform_report if platform_report else None,
        sweep_run=sweep_report if sweep_report else None,
        selected_best=selected_best if selected_best else None,
        selected_best_source=selected_best_source,
    )
    final_gate_params = _resolve_strategy_gate_params(
        config,
        explicit_params=preflight_params,
        report=report,
    )
    release_decision["strategy_gate"] = _strategy_gate_summary(
        preflight_strategy,
        final_gate_params,
        gate_root,
        load_strategy_gate(
            preflight_strategy,
            params=final_gate_params,
            gate_root=gate_root,
        ),
        required_stage=required_stage,
    )
    report["release_decision"] = release_decision

    if args.preflight_json:
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    else:
        logger.info("Preflight completed")
        logger.info(f"overall={report['overall']}")
        logger.info(f"advice_level={advice_level}")
        logger.info(f"checks: total={report['summary']['total']} pass={report['summary']['passed']} warn={report['summary']['warn']} fail={report['summary']['failed']} skip={report['summary']['skipped']}")
        for item in strategy_advice:
            logger.info(f"[strategy-advice] {item}")

        if isinstance(candidate_plan, dict) and candidate_plan:
            logger.info(f"candidate_plan={json.dumps(candidate_plan, ensure_ascii=False)}")
        if isinstance(candidate_grid, list) and candidate_grid:
            logger.info(f"candidate_grid={json.dumps(candidate_grid[:5], ensure_ascii=False)}")
        if sweep_report:
            logger.info(f"preflight_sweep={json.dumps(sweep_report, ensure_ascii=False)}")
            if isinstance(sweep_report, dict) and sweep_report.get("best"):
                logger.info(f"best_candidate={json.dumps(sweep_report['best'], ensure_ascii=False)}")
                if sweep_report.get("recommended_replay"):
                    logger.info(f"recommended_replay={json.dumps(sweep_report['recommended_replay'], ensure_ascii=False)}")
                logger.info("建议优先复用 best candidate 进行下一轮完整预检。")
        if platform_report:
            logger.info(f"preflight_platform={json.dumps(platform_report, ensure_ascii=False)}")
        logger.info(f"release_decision={json.dumps(release_decision, ensure_ascii=False, default=str)}")

    # Persist preflight output for audit and replay workflows.
    if getattr(args, "preflight_export", None):
        try:
            with open(args.preflight_export, "w", encoding="utf-8") as fp:
                json.dump(report, fp, ensure_ascii=False, indent=2, default=str)
            logger.info(f"preflight report saved: {args.preflight_export}")
        except Exception as exc:
            logger.error(f"Failed to write preflight_export file: {exc}")
            if preflight_mode == "live" and not getattr(args, "preflight_allow_block", False):
                return False, release_decision

    # Strict mode: for live launch, enforce advisory level explicitly.
    if preflight_mode == "live":
        if advice_level == "block" and not getattr(args, "preflight_allow_block", False):
            logger.error("Live mode blocked by preflight advisory level: block.")
            return False, release_decision
        if advice_level == "warn" and not getattr(args, "preflight_allow_warn", False):
            logger.error("Live mode reached advisory level: warn. Use --preflight-allow-warn to continue.")
            return False, release_decision

    if report["overall"] != "healthy":
        logger.error("Preflight failed; aborting startup.")
        return False, release_decision

    paper_gate_ready = False
    if _paper_smoke_passed(report):
        gate_payload = promote_strategy_gate(
            preflight_strategy,
            "paper_validated",
            params=final_gate_params,
            gate_root=gate_root,
            source="startup.preflight.paper",
            details={
                "mode": preflight_mode,
                "overall": report.get("overall"),
                "advice_level": advice_level,
                "decision_state": release_decision.get("decision_state"),
            },
            artifacts={"preflight_export": args.preflight_export} if args.preflight_export else {},
        )
        paper_gate_ready = True
        release_decision["strategy_gate"] = _strategy_gate_summary(
            preflight_strategy,
            final_gate_params,
            gate_root,
            gate_payload,
            required_stage=required_stage,
        )
    elif preflight_mode == "live":
        existing_gate = load_strategy_gate(
            preflight_strategy,
            params=final_gate_params,
            gate_root=gate_root,
        )
        paper_gate_ready = existing_gate is not None and build_strategy_gate_summary(existing_gate).get("current_stage_index", 0) >= 3

    if preflight_mode == "live" and paper_gate_ready:
        gate_payload = promote_strategy_gate(
            preflight_strategy,
            "live_candidate",
            params=final_gate_params,
            gate_root=gate_root,
            source="startup.preflight.live",
            details={
                "mode": preflight_mode,
                "overall": report.get("overall"),
                "advice_level": advice_level,
                "decision_state": release_decision.get("decision_state"),
            },
            artifacts={"preflight_export": args.preflight_export} if args.preflight_export else {},
        )
        release_decision["strategy_gate"] = _strategy_gate_summary(
            preflight_strategy,
            final_gate_params,
            gate_root,
            gate_payload,
            required_stage=required_stage,
        )

    return release_decision.get("decision_state") != "block", release_decision


def main():
    global logger
    
    parser = argparse.ArgumentParser(description="生产环境启动脚本")
    parser.add_argument("--config", default=None, help="配置文件路径")
    parser.add_argument("--mode", choices=["backtest", "paper", "live"], default="backtest",
                       help="运行模式")
    parser.add_argument("--skip-health-check", action="store_true",
                       help="跳过健康检查")
    parser.add_argument("--preflight", action="store_true",
                       help="启动前执行生产上线预检（包含健康检查+策略/回放自检）")
    parser.add_argument("--preflight-mode", choices=["backtest", "paper", "live"],
                       help="预检使用的运行模式（默认同 --mode）")
    parser.add_argument("--preflight-strategy", default=None,
                       help="预检策略名（默认使用 config.strategy.name）")
    parser.add_argument("--preflight-symbols", nargs="+",
                       default=None, help="预检标的代码（空格分隔）")
    parser.add_argument("--preflight-start", default=None,
                       help="预检时间窗口起始日期 YYYY-MM-DD")
    parser.add_argument("--preflight-end", default=None,
                       help="预检时间窗口结束日期 YYYY-MM-DD")
    parser.add_argument("--preflight-source", default=None,
                       help="预检数据源（akshare/yfinance/tushare/qlib）")
    parser.add_argument("--preflight-cache-dir", default=None,
                       help="预检数据缓存目录")
    parser.add_argument("--preflight-params", default=None,
                       help="预检策略参数 JSON（例如 '{\"fast\": 8, \"slow\": 17}')")
    parser.add_argument("--preflight-skip-backtest", action="store_true",
                       help="跳过预检中的回测烟雾测试")
    parser.add_argument("--preflight-skip-paper", action="store_true",
                       help="跳过预检中的实盘回放烟雾测试")
    parser.add_argument("--preflight-decision-only", action="store_true",
                       help="仅执行预检并输出上线决策，不启动服务")
    parser.add_argument("--preflight-fail-on-review", action="store_true",
                       help="在决策为 review 时以非 0 码中止（用于严格 CI/脚本闸门）")
    parser.add_argument("--preflight-decision-file", default=None,
                       help="将 release_decision 写入 JSON 文件")
    parser.add_argument("--preflight-decision-seed-file", default="report/preflight_decision_latest.json",
                       help="上轮 release_decision（含 recommended_replay.params）用于本轮参数回填")
    parser.add_argument("--preflight-auto-regression", action="store_true",
                       help="review 并带有 recommended_replay 时，自动开启下一轮预检复测（读取上轮决策快照参数）")
    parser.add_argument("--preflight-auto-rounds", type=int, default=3,
                       help="自动复测最大轮次（仅在 preflight-auto-regression 开启时生效）")
    parser.add_argument("--preflight-allow-warn", action="store_true",
                       help="允许预检处于 warn 级别后仍继续启动")
    parser.add_argument("--preflight-allow-block", action="store_true",
                       help="允许预检处于 block 级别后仍继续启动（实盘谨慎使用）")
    parser.add_argument("--preflight-platform-run", action="store_true",
                       help="启动“自动实验平台化”运行，复测 base + candidate 参数集合")
    parser.add_argument("--preflight-platform-dir", default="report/preflight_platform",
                       help="实验平台落盘目录（默认 report/preflight_platform）")
    parser.add_argument("--preflight-platform-limit", type=int, default=5,
                       help="实验平台候选上限，包含基础参数+候选参数")
    parser.add_argument("--preflight-sweep", action="store_true",
                       help="按 candidate_grid 执行小规模预检复检（默认 3 个候选）")
    parser.add_argument("--preflight-sweep-limit", type=int, default=3,
                       help="预检复检候选数量上限")
    parser.add_argument("--preflight-use-best", action="store_true",
                       help="候选复检完成后以最优参数复跑一次作为最终预检依据")
    parser.add_argument("--preflight-export", default=None,
                       help="将预检报告保存到指定 JSON 文件")
    parser.add_argument("--preflight-alignment-threshold", type=float, default=0.03,
                       help="回测与回放 NAV 漂移告警阈值")
    parser.add_argument("--preflight-alignment-fail-threshold", type=float, default=0.10,
                       help="回测与回放 NAV 漂移硬失败阈值")
    parser.add_argument("--preflight-json", action="store_true",
                       help="仅输出 JSON 格式的预检报告")
    parser.add_argument("--preflight-gate-root", default=DEFAULT_STRATEGY_GATE_ROOT,
                       help="策略阶段门禁 registry 根目录")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                       help="日志级别")
    
    args = parser.parse_args()
    
    # 初始化日志（早期，使用默认配置）
    configure_logging(level=args.log_level)
    logger = get_logger("startup")
    
    logger.info("=" * 60)
    logger.info("量化交易系统 - 生产环境启动")
    logger.info("=" * 60)
    
    try:
        # 加载配置
        config = load_configuration(args.config)
        
        # 重新配置日志（使用配置文件中的设置）
        log_config = config.logging
        configure_logging(
            level=log_config.level,
            json_format=log_config.format == "json",
            log_file=log_config.file
        )
        logger = get_logger("startup")
        
        # 初始化目录
        initialize_directories()
        
        # 健康检查
        preflight_passed = True
        preflight_rounds = 1
        release_decision: Dict[str, Any] = {}
        if args.preflight_decision_only:
            preflight_passed, release_decision, preflight_rounds = (
                _run_preflight_decision_only_cycles(config, args)
            )
        else:
            preflight_passed, release_decision = _run_preflight_if_requested(config, args)

        if args.preflight_decision_only:
            decision_state = str(release_decision.get("decision_state", "unknown")).lower()
            if decision_state == "block":
                logger.error("Decision-only mode blocked by release decision.")
                sys.exit(1)
            if decision_state == "review" and args.preflight_fail_on_review:
                logger.error("Decision-only mode blocked by strict review policy.")
                sys.exit(1)

            if preflight_rounds > 1:
                logger.info(f"Decision-only mode completed: {decision_state} (rounds={preflight_rounds})")
            else:
                logger.info(f"Decision-only mode completed: {decision_state}")
            sys.exit(0)
        if not preflight_passed:
            sys.exit(1)

        if not args.skip_health_check and not args.preflight:
            if not run_health_check():
                logger.error("Health checks failed. Exiting.")
                sys.exit(1)
        else:
            logger.warning("Skipping health checks (--skip-health-check)")
        
        # 设置信号处理
        setup_signal_handlers()
        
        # 根据模式启动
        if args.mode == "backtest":
            start_backtest_mode(config)
        elif args.mode == "paper":
            start_paper_trading_mode(config)
        elif args.mode == "live":
            try:
                _require_live_launch_gate(config, args)
            except MissingStrategyGateStage as exc:
                logger.error("Live launch blocked by strategy gate: %s", exc)
                sys.exit(1)
            start_live_trading_mode(config)
            gate_payload = _mark_live_production_gate(config, args)
            logger.info(
                "Strategy gate promoted: %s (%s)",
                gate_payload.get("current_stage"),
                gate_payload.get("params_signature"),
            )
        
        logger.info("System started successfully")
        logger.info("Press Ctrl+C to stop")
        
        # 保持运行（实际应用中可能是事件循环）
        import time
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
    
    except Exception as e:
        logger.exception("Failed to start system")
        sys.exit(1)


if __name__ == "__main__":
    main()
