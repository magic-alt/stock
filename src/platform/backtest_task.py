"""
Backtest task runner used by the platform job queue.
"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

from src.backtest.engine import BacktestEngine
from src.backtest.plotting import plot_backtest_with_indicators
from src.backtest.repro import build_snapshot_payload, compute_report_signature, write_snapshot
from src.data_sources.quality import save_quality_report
from src.platform.data_lake import DataLake


def _build_report_dir(payload: Dict[str, Any]) -> str:
    if payload.get("report_dir"):
        return payload["report_dir"]
    symbols = payload.get("symbols") or []
    symbol_part = "_".join(symbols) if symbols else "unknown"
    symbol_part = symbol_part.replace(".SH", "").replace(".SZ", "").replace(".", "_")
    strategy = payload.get("strategy", "run")
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    return os.path.join("report", f"{symbol_part}_{strategy}_{timestamp}")


def _build_repro_command(payload: Dict[str, Any]) -> str:
    params = payload.get("params")
    tokens = [
        "python",
        "unified_backtest_framework.py",
        "run",
        "--strategy",
        str(payload.get("strategy", "unknown")),
        "--symbols",
    ]
    tokens.extend(payload.get("symbols") or [])
    tokens.extend(["--start", str(payload.get("start")), "--end", str(payload.get("end"))])
    tokens.extend(["--source", str(payload.get("source", "akshare"))])
    if payload.get("benchmark"):
        tokens.extend(["--benchmark", str(payload["benchmark"])])
    if payload.get("benchmark_source"):
        tokens.extend(["--benchmark_source", str(payload["benchmark_source"])])
    if params:
        import json
        tokens.extend(["--params", json.dumps(params, ensure_ascii=False)])
    tokens.extend(["--cash", str(payload.get("cash", 200000))])
    tokens.extend(["--commission", str(payload.get("commission", 0.0001))])
    tokens.extend(["--slippage", str(payload.get("slippage", 0.0005))])
    if payload.get("adj"):
        tokens.extend(["--adj", str(payload["adj"])])
    if payload.get("cache_dir"):
        tokens.extend(["--cache_dir", str(payload["cache_dir"])])
    if payload.get("calendar_mode"):
        tokens.extend(["--calendar", str(payload["calendar_mode"])])
    if payload.get("plot"):
        tokens.append("--plot")
    return " ".join(tokens)


def run_backtest_job(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run a single backtest task and optionally generate a report."""
    engine = BacktestEngine(
        source=payload.get("source", "akshare"),
        benchmark_source=payload.get("benchmark_source") or payload.get("source", "akshare"),
        cache_dir=payload.get("cache_dir", "./cache"),
        calendar_mode=payload.get("calendar_mode", "fill"),
    )
    metrics = engine.run_strategy(
        payload.get("strategy", "turning_point"),
        payload.get("symbols") or [],
        payload.get("start"),
        payload.get("end"),
        params=payload.get("params"),
        cash=float(payload.get("cash", 200000)),
        commission=float(payload.get("commission", 0.0001)),
        slippage=float(payload.get("slippage", 0.0005)),
        benchmark=payload.get("benchmark"),
        adj=payload.get("adj"),
        out_dir=payload.get("out_dir"),
        enable_plot=bool(payload.get("plot", False)),
        calendar_mode=payload.get("calendar_mode"),
        collect_diagnostics=True,
    )
    cerebro = metrics.pop("_cerebro", None)
    quality_report = metrics.pop("_quality_report", None)
    data_fingerprint = metrics.pop("_data_fingerprint", None)
    nav = metrics.pop("nav", None)

    report_dir = _build_report_dir(payload)
    repro_command = _build_repro_command(payload)
    snapshot_payload = build_snapshot_payload(
        run_config=payload,
        metrics={k: v for k, v in metrics.items()},
        data_fingerprint=data_fingerprint or {},
        quality_report=quality_report,
        repro_command=repro_command,
    )
    report_signature = compute_report_signature(snapshot_payload)
    snapshot_payload["report_signature"] = report_signature
    snapshot_path = write_snapshot(report_dir, snapshot_payload)
    if quality_report:
        save_quality_report(report_dir, quality_report)

    report_path = None
    if payload.get("plot") and cerebro is not None:
        report_path = plot_backtest_with_indicators(
            cerebro,
            style="candlestick",
            show_indicators=True,
            figsize=(16, 10),
            auto_save=True,
            strategy_name=str(payload.get("strategy", "strategy")),
            symbols=payload.get("symbols"),
            metrics=metrics,
            report_dir=report_dir,
            repro_command=repro_command,
            report_signature=report_signature,
            snapshot_path=snapshot_path,
        )

    lake_entry = None
    if payload.get("register_data_lake", True):
        lake = DataLake(base_dir=payload.get("data_lake_dir", "./data_lake"))
        lake_entry = lake.register(
            kind="backtest_report",
            name=f"{payload.get('strategy', 'strategy')}",
            path=report_dir,
            metadata={"report_signature": report_signature},
        )

    return {
        "report_dir": report_path or report_dir,
        "snapshot_path": snapshot_path,
        "data_lake_entry": lake_entry.entry_id if lake_entry else None,
        "metrics": metrics,
        "has_nav": nav is not None,
    }
