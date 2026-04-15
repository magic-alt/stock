# unified_backtest_framework.py
"""
Unified Backtest Framework - CLI Entry Point

This is the simplified main entry point after Phase 2 modularization.
All core functionality has been moved to:
- src/data_sources/providers.py - Data providers
- src/backtest/strategy_modules.py - Strategy definitions  
- src/backtest/engine.py - Backtest engine and optimization
- src/backtest/plotting.py - Visualization
- src/backtest/analysis.py - Analysis tools
"""
from __future__ import annotations

import argparse
import json
import os
import time
from typing import Any, Dict, Optional

# Import modularized components
from src.backtest.admission import (
    ADMISSION_PROFILES,
    DEFAULT_STRATEGY_BASELINE_ROOT,
    evaluate_admission,
    generate_historical_baseline,
    load_sample_cases,
    register_strategy_baseline,
    resolve_baseline_snapshot,
    write_admission_artifacts,
    write_baseline_artifacts,
)
from src.data_sources.providers import get_provider, PROVIDER_NAMES
from src.backtest.strategy_modules import STRATEGY_REGISTRY
from src.backtest.engine import BacktestEngine
from src.backtest.plotting import plot_backtest_with_indicators
from src.backtest.repro import build_repro_command, build_snapshot_payload, compute_report_signature, write_snapshot
from src.data_sources.quality import save_quality_report
from src.optimizer.combo_optimizer import load_nav_series, optimize_portfolio
from src.core.logger import get_logger

# Default cache directory
CACHE_DEFAULT = "./cache"

logger = get_logger("unified_cli")


def _build_report_dir(args: argparse.Namespace) -> str:
    """Return output directory for reports/snapshots."""
    if getattr(args, "out_dir", None):
        return args.out_dir
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    command = getattr(args, "command", "run")
    strategy = getattr(args, "strategy", "run")
    if command in {"baseline", "admission"}:
        return os.path.join("report", f"{strategy}_{command}_{timestamp}")
    symbol_part = "_".join(args.symbols) if getattr(args, "symbols", None) else "unknown"
    symbol_part = symbol_part.replace(".SH", "").replace(".SZ", "").replace(".", "_")
    return os.path.join("report", f"{symbol_part}_{strategy}_{timestamp}")


def _parse_json_option(value: Optional[str], *, option_name: str) -> Optional[Dict[str, Any]]:
    """Parse a JSON CLI option into a dictionary."""
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON for {option_name}: {exc}") from exc
    if parsed is None:
        return None
    if not isinstance(parsed, dict):
        raise ValueError(f"{option_name} must be a JSON object.")
    return parsed


def _log_artifacts(title: str, artifacts: Dict[str, str]) -> None:
    """Log generated artifact paths."""
    logger.info(title)
    for name, path in artifacts.items():
        logger.info(f"- {name}: {path}")


def parse_args() -> argparse.Namespace:
    """Build the CLI interface and return parsed arguments."""
    parser = argparse.ArgumentParser(description="Unified akshare/yfinance/tushare backtest framework")
    sub = parser.add_subparsers(dest="command", required=True)

    # ===== run command =====
    run_p = sub.add_parser("run", help="Run a single strategy backtest")
    run_p.add_argument("--strategy", default="turning_point", choices=sorted(STRATEGY_REGISTRY.keys()))
    run_p.add_argument("--symbols", nargs="+", required=True)
    run_p.add_argument("--start", required=True)
    run_p.add_argument("--end", required=True)
    run_p.add_argument("--source", default="akshare", choices=sorted(PROVIDER_NAMES))
    run_p.add_argument("--benchmark", default=None)
    run_p.add_argument("--benchmark_source", default=None)
    run_p.add_argument("--params", default=None, help="JSON string of strategy params")
    run_p.add_argument("--cash", type=float, default=200000)
    run_p.add_argument("--commission", type=float, default=0.0001)
    run_p.add_argument("--slippage", type=float, default=0.0005)
    run_p.add_argument("--adj", default=None)
    run_p.add_argument("--out_dir", default=None)
    run_p.add_argument("--cache_dir", default=CACHE_DEFAULT)
    run_p.add_argument("--calendar", choices=["off", "fill"], default="fill",
                       help="Trading calendar alignment (off/fill)")
    run_p.add_argument("--plot", action="store_true", help="Display backtest chart with technical indicators")
    run_p.add_argument("--fee-config", dest="fee_config", default=None, 
                       help="Fee plugin name (e.g., 'cn_stock'). If not specified, uses default commission.")
    run_p.add_argument("--fee-params", dest="fee_params", default=None,
                       help='Fee plugin parameters as JSON string (e.g., \'{"commission_rate":0.0001,"min_commission":5.0}\')')

    # ===== baseline command =====
    baseline_p = sub.add_parser("baseline", help="Generate historical regression baseline snapshots")
    baseline_p.add_argument("--strategy", required=True, choices=sorted(STRATEGY_REGISTRY.keys()))
    baseline_p.add_argument("--params", default=None, help="JSON string of strategy params")
    baseline_p.add_argument("--samples-file", default=None, help="YAML/JSON file with historical sample cases")
    baseline_p.add_argument("--samples", nargs="*", default=None, help="Optional sample ids to run")
    baseline_p.add_argument("--regimes", nargs="*", default=None, help="Optional regime tags to run (bull/bear/range/high-vol)")
    baseline_p.add_argument("--source", default=None, choices=sorted(PROVIDER_NAMES),
                            help="Override the source for all selected sample cases")
    baseline_p.add_argument("--benchmark_source", default=None, choices=sorted(PROVIDER_NAMES),
                            help="Override the benchmark source for all selected sample cases")
    baseline_p.add_argument("--cash", type=float, default=200000)
    baseline_p.add_argument("--commission", type=float, default=0.0001)
    baseline_p.add_argument("--slippage", type=float, default=0.0005)
    baseline_p.add_argument("--adj", default=None)
    baseline_p.add_argument("--out_dir", default=None)
    baseline_p.add_argument("--cache_dir", default=CACHE_DEFAULT)
    baseline_p.add_argument("--baseline-root", default=DEFAULT_STRATEGY_BASELINE_ROOT,
                            help="Root directory for registered single-strategy baselines")
    baseline_p.add_argument("--baseline-alias", default="default",
                            help="Alias under the strategy baseline registry")
    baseline_p.add_argument("--register-strategy-baseline", action="store_true",
                            help="Register this snapshot as the canonical baseline for the strategy/alias")
    baseline_p.add_argument("--calendar", choices=["off", "fill"], default=None,
                            help="Override trading calendar alignment for selected samples")

    # ===== admission command =====
    admission_p = sub.add_parser("admission", help="Evaluate strategy admission against historical sample gates")
    admission_p.add_argument("--strategy", required=True, choices=sorted(STRATEGY_REGISTRY.keys()))
    admission_p.add_argument("--params", default=None, help="JSON string of strategy params")
    admission_p.add_argument("--samples-file", default=None, help="YAML/JSON file with historical sample cases")
    admission_p.add_argument("--samples", nargs="*", default=None, help="Optional sample ids to run")
    admission_p.add_argument("--regimes", nargs="*", default=None, help="Optional regime tags to run (bull/bear/range/high-vol)")
    admission_p.add_argument("--baseline-file", default=None, help="Optional stored baseline JSON for regression checks")
    admission_p.add_argument("--profile", default="institutional", choices=sorted(ADMISSION_PROFILES.keys()))
    admission_p.add_argument("--source", default=None, choices=sorted(PROVIDER_NAMES),
                             help="Override the source for all selected sample cases")
    admission_p.add_argument("--benchmark_source", default=None, choices=sorted(PROVIDER_NAMES),
                             help="Override the benchmark source for all selected sample cases")
    admission_p.add_argument("--cash", type=float, default=200000)
    admission_p.add_argument("--commission", type=float, default=0.0001)
    admission_p.add_argument("--slippage", type=float, default=0.0005)
    admission_p.add_argument("--adj", default=None)
    admission_p.add_argument("--out_dir", default=None)
    admission_p.add_argument("--cache_dir", default=CACHE_DEFAULT)
    admission_p.add_argument("--baseline-root", default=DEFAULT_STRATEGY_BASELINE_ROOT,
                             help="Root directory for registered single-strategy baselines")
    admission_p.add_argument("--baseline-alias", default="default",
                             help="Alias under the strategy baseline registry to resolve when --baseline-file is omitted")
    admission_p.add_argument("--calendar", choices=["off", "fill"], default=None,
                             help="Override trading calendar alignment for selected samples")

    # ===== grid command =====
    grid_p = sub.add_parser("grid", help="Run grid search for a strategy")
    grid_p.add_argument("--strategy", required=True, choices=sorted(STRATEGY_REGISTRY.keys()))
    grid_p.add_argument("--symbols", nargs="+", required=True)
    grid_p.add_argument("--start", required=True)
    grid_p.add_argument("--end", required=True)
    grid_p.add_argument("--grid", required=False, default=None, help="JSON like {'period':[10,20]} (defaults to module grid)")
    grid_p.add_argument("--source", default="akshare", choices=sorted(PROVIDER_NAMES))
    grid_p.add_argument("--benchmark", default=None)
    grid_p.add_argument("--benchmark_source", default=None)
    grid_p.add_argument("--cash", type=float, default=200000)
    grid_p.add_argument("--commission", type=float, default=0.0001)
    grid_p.add_argument("--slippage", type=float, default=0.0005)
    grid_p.add_argument("--adj", default=None)
    grid_p.add_argument("--cache_dir", default=CACHE_DEFAULT)
    grid_p.add_argument("--calendar", choices=["off", "fill"], default="fill",
                        help="Trading calendar alignment (off/fill)")
    grid_p.add_argument("--out_csv", default=None)
    grid_p.add_argument("--workers", type=int, default=1)
    grid_p.add_argument("--fee-config", dest="fee_config", default=None,
                        help="Fee plugin name (e.g., 'cn_stock')")
    grid_p.add_argument("--fee-params", dest="fee_params", default=None,
                        help='Fee plugin parameters as JSON string')

    # ===== auto command =====
    auto_p = sub.add_parser("auto", help="Run multi-strategy optimisation + Pareto + Top-N")
    auto_p.add_argument("--symbols", nargs="+", required=True)
    auto_p.add_argument("--start", required=True)
    auto_p.add_argument("--end", required=True)
    auto_p.add_argument("--source", default="akshare", choices=sorted(PROVIDER_NAMES))
    auto_p.add_argument("--benchmark", default="000300.SH")
    auto_p.add_argument("--benchmark_source", default=None)
    auto_p.add_argument("--strategies", nargs="*", default=None, choices=sorted(STRATEGY_REGISTRY.keys()))
    auto_p.add_argument("--top_n", type=int, default=5)
    auto_p.add_argument("--min_trades", type=int, default=1,
                        help="Require at least this many closed trades when selecting Top-N for replay/plot")
    auto_p.add_argument("--cash", type=float, default=200000)
    auto_p.add_argument("--commission", type=float, default=0.0001)
    auto_p.add_argument("--slippage", type=float, default=0.001)
    auto_p.add_argument("--adj", default=None)
    auto_p.add_argument("--cache_dir", default=CACHE_DEFAULT)
    auto_p.add_argument("--out_dir", default="./reports_auto")
    auto_p.add_argument("--calendar", choices=["off", "fill"], default="fill",
                        help="Trading calendar alignment (off/fill)")
    auto_p.add_argument("--workers", type=int, default=1)
    auto_p.add_argument("--hot_only", action="store_true", help="Use narrowed hot-zone parameter grids for strategies")
    auto_p.add_argument("--use_benchmark_regime", action="store_true",
                        help="Use benchmark EMA200 as bull regime filter (see --regime_scope)")
    auto_p.add_argument("--regime_scope", default="trend", choices=["trend", "all", "none"],
                        help="Apply regime filter to: trend strategies only (ema/macd/turning_point), or all, or none.")
    auto_p.add_argument("--fee-config", dest="fee_config", default=None,
                        help="Fee plugin name (e.g., 'cn_stock')")
    auto_p.add_argument("--fee-params", dest="fee_params", default=None,
                        help='Fee plugin parameters as JSON string')

    # ===== combo command =====
    combo_p = sub.add_parser("combo", help="Optimize combination weights from NAV CSVs")
    combo_p.add_argument("--navs", nargs="+", required=True, help="List of NAV csv files (with 'nav' column)")
    combo_p.add_argument("--names", nargs="*", default=None, help="Optional names for each NAV")
    combo_p.add_argument("--objective", default="sharpe", choices=["sharpe", "return", "drawdown"])
    combo_p.add_argument("--step", type=float, default=0.25, help="Grid search step for weights")
    combo_p.add_argument("--allow_short", action="store_true", help="Allow negative weights in grid search")
    combo_p.add_argument("--max_weight", type=float, default=1.0, help="Max absolute weight per leg")
    combo_p.add_argument("--risk_free", type=float, default=0.0, help="Daily risk-free rate for Sharpe")
    combo_p.add_argument("--out", default=None, help="Optional path to save combined NAV csv")

    # ===== list command =====
    sub.add_parser("list", help="List registered strategies", aliases=["list-strategies"])

    return parser.parse_args()


def main() -> None:
    """Entrypoint used by the console script or direct module execution."""
    args = parse_args()
    
    # ===== list command =====
    if args.command in {"list", "list-strategies"}:
        logger.info("Available strategies:")
        for name, module in STRATEGY_REGISTRY.items():
            logger.info(f"- {name}: {module.description}")
        return

    # ===== combo command =====
    if args.command == "combo":
        names = args.names or [os.path.splitext(os.path.basename(p))[0] for p in args.navs]
        if len(names) != len(args.navs):
            logger.error("names length must match navs length")
            return
        nav_map = {name: load_nav_series(path) for name, path in zip(names, args.navs)}
        result = optimize_portfolio(
            nav_map,
            step=args.step,
            objective=args.objective,
            allow_short=args.allow_short,
            max_weight=args.max_weight,
            risk_free=args.risk_free,
        )
        payload = {
            "weights": result.weights,
            "stats": result.stats,
        }
        logger.info(json.dumps(payload, indent=2, default=float))
        if args.out:
            result.nav.to_csv(args.out)
        return

    # ===== run command =====
    if args.command == "run":
        try:
            params = _parse_json_option(args.params, option_name="--params")
        except ValueError as exc:
            logger.error(str(exc))
            return
        
        # V2.9.0: Parse fee plugin parameters
        fee_plugin = args.fee_config if hasattr(args, 'fee_config') else None
        fee_plugin_params = None
        if hasattr(args, 'fee_params') and args.fee_params:
            try:
                fee_plugin_params = _parse_json_option(args.fee_params, option_name="--fee-params")
            except ValueError as exc:
                logger.error(str(exc))
                return
        
        engine = BacktestEngine(
            source=args.source,
            benchmark_source=args.benchmark_source or args.source,
            cache_dir=args.cache_dir,
            calendar_mode=args.calendar,
        )
        metrics = engine.run_strategy(
            args.strategy,
            args.symbols,
            args.start,
            args.end,
            params=params,
            cash=args.cash,
            commission=args.commission,
            slippage=args.slippage,
            benchmark=args.benchmark,
            adj=args.adj,
            out_dir=args.out_dir,
            enable_plot=args.plot,
            fee_plugin=fee_plugin,
            fee_plugin_params=fee_plugin_params,
            calendar_mode=args.calendar,
            collect_diagnostics=True,
        )
        nav = metrics.pop("nav")
        cerebro = metrics.pop("_cerebro", None)
        quality_report = metrics.pop("_quality_report", None)
        data_fingerprint = metrics.pop("_data_fingerprint", None)
        
        logger.info(json.dumps({k: v for k, v in metrics.items() if k != "nav"}, indent=2, default=float))

        report_dir = _build_report_dir(args)
        os.makedirs(report_dir, exist_ok=True)
        if args.out_dir:
            nav.to_csv(os.path.join(report_dir, f"{args.strategy}_nav.csv"))
        
        run_config = {
            "strategy": args.strategy,
            "symbols": args.symbols,
            "start": args.start,
            "end": args.end,
            "source": args.source,
            "benchmark": args.benchmark,
            "benchmark_source": args.benchmark_source or args.source,
            "params": params or {},
            "cash": args.cash,
            "commission": args.commission,
            "slippage": args.slippage,
            "adj": args.adj,
            "calendar_mode": args.calendar,
            "cache_dir": args.cache_dir,
        }
        repro_command = build_repro_command(args)
        snapshot_payload = build_snapshot_payload(
            run_config=run_config,
            metrics={k: v for k, v in metrics.items() if k != "nav"},
            data_fingerprint=data_fingerprint or {},
            quality_report=quality_report,
            repro_command=repro_command,
        )
        report_signature = compute_report_signature(snapshot_payload)
        snapshot_payload["report_signature"] = report_signature
        snapshot_path = write_snapshot(report_dir, snapshot_payload)
        if quality_report:
            save_quality_report(report_dir, quality_report)

        # Plot if enabled and cerebro is available
        if args.plot and cerebro:
            # 自动保存模式：保存到report目录
            report_dir = plot_backtest_with_indicators(
                cerebro,
                style='candlestick',
                show_indicators=True,
                figsize=(16, 10),
                out_file=None,  # 不使用传统out_file
                auto_save=True,  # 启用自动保存
                strategy_name=args.strategy,
                symbols=args.symbols,
                metrics=metrics,  # 传递性能指标
                report_dir=report_dir,
                repro_command=repro_command,
                report_signature=report_signature,
                snapshot_path=snapshot_path,
            )
            if report_dir:
                logger.info(f"[报告] 详细报告已保存到: {report_dir}")
        return

    # ===== baseline command =====
    if args.command == "baseline":
        try:
            params = _parse_json_option(args.params, option_name="--params")
            sample_cases = load_sample_cases(args.samples_file)
        except (OSError, ValueError) as exc:
            logger.error(str(exc))
            return

        snapshot = generate_historical_baseline(
            args.strategy,
            params=params,
            sample_cases=sample_cases,
            sample_ids=args.samples,
            regimes=args.regimes,
            cash=args.cash,
            commission=args.commission,
            slippage=args.slippage,
            cache_dir=args.cache_dir,
            source_override=args.source,
            benchmark_source_override=args.benchmark_source,
            calendar_override=args.calendar,
            adj_override=args.adj,
        )
        report_dir = _build_report_dir(args)
        artifacts = write_baseline_artifacts(report_dir, snapshot)
        logger.info(json.dumps(snapshot, indent=2))
        _log_artifacts("Historical baseline artifacts:", artifacts)
        if args.register_strategy_baseline:
            registry_artifacts = register_strategy_baseline(
                snapshot,
                baseline_root=args.baseline_root,
                alias=args.baseline_alias,
            )
            _log_artifacts("Registered strategy baseline artifacts:", registry_artifacts)
        return

    # ===== admission command =====
    if args.command == "admission":
        try:
            params = _parse_json_option(args.params, option_name="--params")
            sample_cases = load_sample_cases(args.samples_file)
            baseline_snapshot, baseline_context = resolve_baseline_snapshot(
                args.strategy,
                baseline_file=args.baseline_file,
                baseline_root=args.baseline_root,
                alias=args.baseline_alias,
            )
        except (OSError, ValueError) as exc:
            logger.error(str(exc))
            return

        if baseline_context.get("mode") == "strategy_registry":
            logger.info(
                "Resolved strategy baseline: %s (alias=%s)",
                baseline_context.get("path"),
                baseline_context.get("alias"),
            )
        elif baseline_context.get("mode") == "missing":
            logger.info(
                "No registered strategy baseline found under %s for alias=%s; continuing without regression baseline.",
                args.baseline_root,
                baseline_context.get("alias"),
            )

        current_snapshot = generate_historical_baseline(
            args.strategy,
            params=params,
            sample_cases=sample_cases,
            sample_ids=args.samples,
            regimes=args.regimes,
            cash=args.cash,
            commission=args.commission,
            slippage=args.slippage,
            cache_dir=args.cache_dir,
            source_override=args.source,
            benchmark_source_override=args.benchmark_source,
            calendar_override=args.calendar,
            adj_override=args.adj,
        )
        report = evaluate_admission(
            current_snapshot,
            profile_name=args.profile,
            baseline_snapshot=baseline_snapshot,
            baseline_context=baseline_context,
        )
        report_dir = _build_report_dir(args)
        snapshot_artifacts = write_baseline_artifacts(
            report_dir,
            current_snapshot,
            prefix="current_historical_snapshot",
        )
        report_artifacts = write_admission_artifacts(report_dir, report)
        logger.info(json.dumps(report, indent=2))
        _log_artifacts("Historical snapshot artifacts:", snapshot_artifacts)
        _log_artifacts("Admission report artifacts:", report_artifacts)
        return

    # ===== grid command =====
    if args.command == "grid":
        engine = BacktestEngine(
            source=args.source,
            benchmark_source=args.benchmark_source or args.source,
            cache_dir=args.cache_dir,
            calendar_mode=args.calendar,
        )
        module = STRATEGY_REGISTRY[args.strategy]
        grid = json.loads(args.grid) if args.grid else module.grid_defaults
        df = engine.grid_search(
            args.strategy,
            grid,
            args.symbols,
            args.start,
            args.end,
            cash=args.cash,
            commission=args.commission,
            slippage=args.slippage,
            benchmark=args.benchmark,
            adj=args.adj,
            max_workers=args.workers,
            calendar_mode=args.calendar,
        )
        if args.out_csv:
            df.to_csv(args.out_csv, index=False)
        else:
            logger.info(df.head().to_string())
        return

    # ===== auto command =====
    if args.command == "auto":
        engine = BacktestEngine(
            source=args.source,
            benchmark_source=args.benchmark_source or args.source,
            cache_dir=args.cache_dir,
            calendar_mode=args.calendar,
        )
        engine.auto_pipeline(
            args.symbols,
            args.start,
            args.end,
            strategies=args.strategies,
            benchmark=args.benchmark,
            top_n=args.top_n,
            min_trades=args.min_trades,
            cash=args.cash,
            commission=args.commission,
            slippage=args.slippage,
            adj=args.adj,
            out_dir=args.out_dir,
            workers=args.workers,
            hot_only=args.hot_only,
            use_benchmark_regime=args.use_benchmark_regime,
            regime_scope=args.regime_scope,
            calendar_mode=args.calendar,
        )
        logger.info(f"Pipeline completed. Results saved to {args.out_dir}")
        return


if __name__ == "__main__":  # pragma: no cover
    main()
