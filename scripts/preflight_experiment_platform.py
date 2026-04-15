#!/usr/bin/env python3
"""
Preflight experiment platform helper.

Provide light-weight batched execution and persistent artifacts for strategy
preflight optimization experiments (candidate replay batches).
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from scripts.preflight_check import run_preflight_checks


def _safe_float(value: object) -> Optional[float]:
    """Convert a value into float when possible."""
    try:
        if value is None:
            return None
        converted = float(value)
    except (TypeError, ValueError):
        return None
    if converted != converted:
        return None
    return converted


def _normalize_candidates(analysis: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
    """Extract candidate dict list from preflight analysis."""
    candidates: List[Any] = analysis.get("candidate_grid") or []
    if not isinstance(candidates, list):
        candidates = analysis.get("strategy_advice_payload", {}).get("candidate_grid", [])
    if not isinstance(candidates, list):
        return []

    normalized: List[Dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        normalized.append(dict(candidate))
        if len(normalized) >= max(1, int(limit or 0)):
            break

    return normalized


def build_experiment_specs_from_report(
    report: Dict[str, Any],
    strategy: str,
    mode: str,
    *,
    include_base: bool = True,
    max_candidates: int = 5,
) -> List[Dict[str, Any]]:
    """Build executable experiment specs from a preflight report."""
    specs: List[Dict[str, Any]] = []
    analysis = report.get("analysis", {})
    if not isinstance(analysis, dict):
        return specs

    requested = {
        "requested_strategy": report.get("config", {}).get("requested_strategy"),
        "resolved_strategy": report.get("config", {}).get("strategy"),
    }

    if include_base:
        specs.append(
            {
                "experiment_id": "exp_base",
                "label": "base_params",
                "strategy": strategy,
                "mode": mode,
                "params": report.get("config", {}).get("strategy_params_requested", {}),
            }
        )

    candidates = _normalize_candidates(
        analysis=analysis,
        limit=max_candidates,
    )
    for idx, candidate in enumerate(candidates, 1):
        specs.append(
            {
                "experiment_id": f"exp_{idx:02d}",
                "label": f"candidate_{idx:02d}",
                "strategy": strategy,
                "mode": mode,
                "params": candidate,
            }
        )

    return specs


def _run_rank_key(result: Dict[str, Any]) -> tuple:
    """Rank experiments: healthy > warn > block, smaller drift first."""
    analysis = result.get("analysis", {})
    level = str(analysis.get("advice_level", "info")).lower()
    overall = str(result.get("overall", "unhealthy")).lower()
    drift = _safe_float(analysis.get("drift")) or 1.0e9
    level_weight = {"info": 0, "warn": 1, "block": 2}
    overall_weight = 0 if overall == "healthy" else 1
    return (overall_weight, level_weight.get(level, 3), abs(drift))


def run_experiment_batch(
    config,
    preflight_strategy: str,
    specs: List[Dict[str, Any]],
    args,
    *,
    logger=None,
) -> Dict[str, Any]:
    """
    Execute experiments sequentially and return an aggregated result payload.
    """
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    started = time.perf_counter()
    run_dir = getattr(args, "preflight_platform_dir", None) or None
    if run_dir:
        os.makedirs(run_dir, exist_ok=True)

    results: List[Dict[str, Any]] = []
    best = None
    best_key = (1, 3, float("inf"))

    for idx, spec in enumerate(specs, 1):
        if logger:
            logger.info("Experiment %s/%s: %s", idx, len(specs), spec.get("experiment_id"))
        spec_start = time.perf_counter()
        try:
            report = run_preflight_checks(
                config=config,
                strategy=spec.get("strategy", preflight_strategy),
                symbols=args.preflight_symbols,
                start=args.preflight_start,
                end=args.preflight_end,
                source=args.preflight_source or None,
                cache_dir=args.preflight_cache_dir,
                mode=spec.get("mode"),
                cash=float(getattr(config.backtest, "initial_cash", 0.0) or 0.0),
                commission=float(getattr(config.backtest, "commission", 0.0) or 0.0),
                slippage=float(getattr(config.backtest, "slippage", 0.0) or 0.0),
                params=spec.get("params"),
                run_backtest_smoke=not args.preflight_skip_backtest,
                run_paper_smoke=not args.preflight_skip_paper,
                alignment_threshold=args.preflight_alignment_threshold,
                alignment_fail_threshold=args.preflight_alignment_fail_threshold,
            )
            elapsed = round(time.perf_counter() - spec_start, 4)
            analysis = report.get("analysis", {})
            item = {
                "experiment_id": spec.get("experiment_id"),
                "label": spec.get("label"),
                "requested_params": spec.get("params"),
                "overall": report.get("overall"),
                "advice_level": analysis.get("advice_level"),
                "drift": analysis.get("drift"),
                "drift_pct": analysis.get("drift_pct"),
                "elapsed_seconds": elapsed,
                "strategy_advice": analysis.get("strategy_advice", []),
                "candidate_plan": analysis.get("candidate_plan", {}),
                "status": "success",
                "report": report,
            }
            key = _run_rank_key(item)
            if key < best_key:
                best_key = key
                best = item
            results.append(item)
        except Exception as exc:  # pragma: no cover - defensive
            elapsed = round(time.perf_counter() - spec_start, 4)
            item = {
                "experiment_id": spec.get("experiment_id"),
                "label": spec.get("label"),
                "requested_params": spec.get("params"),
                "overall": "error",
                "advice_level": "block",
                "drift": None,
                "elapsed_seconds": elapsed,
                "status": "error",
                "error": str(exc),
            }
            results.append(item)

        if run_dir:
            exp_path = os.path.join(run_dir, f"{run_id}_{spec.get('experiment_id')}.json")
            with open(exp_path, "w", encoding="utf-8") as fp:
                json.dump(item, fp, ensure_ascii=False, indent=2, default=str)

    elapsed_total = round(time.perf_counter() - started, 4)
    passed = len([r for r in results if r.get("overall") == "healthy"])
    blocked = len([r for r in results if str(r.get("overall", "")).lower() == "unhealthy"])
    warning = len([r for r in results if r.get("advice_level") == "warn"])

    return {
        "platform_run_id": run_id,
        "generated_at": datetime.now().isoformat(),
        "spec_count": len(specs),
        "elapsed_seconds": elapsed_total,
        "passed": passed,
        "warning": warning,
        "blocked": blocked,
        "success": len([r for r in results if r.get("status") == "success"]),
        "failed": len([r for r in results if r.get("status") != "success"]),
        "results": results,
        "best": best or {},
    }
