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
from typing import Dict

# Import modularized components
from src.data_sources.providers import get_provider, PROVIDER_NAMES
from src.backtest.strategy_modules import STRATEGY_REGISTRY
from src.backtest.engine import BacktestEngine
from src.backtest.plotting import plot_backtest_with_indicators

# Default cache directory
CACHE_DEFAULT = "./cache"


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
    run_p.add_argument("--slippage", type=float, default=0.001)
    run_p.add_argument("--adj", default=None)
    run_p.add_argument("--out_dir", default=None)
    run_p.add_argument("--cache_dir", default=CACHE_DEFAULT)
    run_p.add_argument("--plot", action="store_true", help="Display backtest chart with technical indicators")

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
    grid_p.add_argument("--out_csv", default=None)
    grid_p.add_argument("--workers", type=int, default=1)

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
    auto_p.add_argument("--workers", type=int, default=1)
    auto_p.add_argument("--hot_only", action="store_true", help="Use narrowed hot-zone parameter grids for strategies")
    auto_p.add_argument("--use_benchmark_regime", action="store_true",
                        help="Use benchmark EMA200 as bull regime filter (see --regime_scope)")
    auto_p.add_argument("--regime_scope", default="trend", choices=["trend", "all", "none"],
                        help="Apply regime filter to: trend strategies only (ema/macd/turning_point), or all, or none.")

    # ===== list command =====
    sub.add_parser("list", help="List registered strategies")

    return parser.parse_args()


def main() -> None:
    """Entrypoint used by the console script or direct module execution."""
    args = parse_args()
    
    # ===== list command =====
    if args.command == "list":
        print("Available strategies:")
        for name, module in STRATEGY_REGISTRY.items():
            print(f"- {name}: {module.description}")
        return

    # ===== run command =====
    if args.command == "run":
        params = json.loads(args.params) if args.params else None
        engine = BacktestEngine(
            source=args.source,
            benchmark_source=args.benchmark_source or args.source,
            cache_dir=args.cache_dir,
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
        )
        nav = metrics.pop("nav")
        cerebro = metrics.pop("_cerebro", None)
        
        print(json.dumps({k: v for k, v in metrics.items() if k != "nav"}, indent=2, default=float))
        
        if args.out_dir:
            os.makedirs(args.out_dir, exist_ok=True)
            nav.to_csv(os.path.join(args.out_dir, f"{args.strategy}_nav.csv"))
        
        # Plot if enabled and cerebro is available
        if args.plot and cerebro:
            out_file = os.path.join(args.out_dir, f"{args.strategy}_chart.png") if args.out_dir else None
            plot_backtest_with_indicators(
                cerebro,
                style='candlestick',
                show_indicators=True,
                figsize=(16, 10),
                out_file=out_file,
            )
        return

    # ===== grid command =====
    if args.command == "grid":
        engine = BacktestEngine(
            source=args.source,
            benchmark_source=args.benchmark_source or args.source,
            cache_dir=args.cache_dir,
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
        )
        if args.out_csv:
            df.to_csv(args.out_csv, index=False)
        else:
            print(df.head())
        return

    # ===== auto command =====
    if args.command == "auto":
        engine = BacktestEngine(
            source=args.source,
            benchmark_source=args.benchmark_source or args.source,
            cache_dir=args.cache_dir,
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
        )
        print(f"Pipeline completed. Results saved to {args.out_dir}")
        return


if __name__ == "__main__":  # pragma: no cover
    main()
