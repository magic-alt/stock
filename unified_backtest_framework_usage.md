# Unified Backtest Framework Usage Guide

This guide explains how to run the `unified_backtest_framework.py` script, configure data sources, and extend the strategy catalogue.

## 1. Prerequisites

- Python 3.9+
- Recommended virtual environment (e.g. `python -m venv .venv`)
- Core dependencies:
  ```bash
  pip install backtrader pandas numpy matplotlib
  ```
- Optional data providers:
  - `pip install akshare` (default provider)
  - `pip install yfinance`
  - `pip install tushare`

> **Note**
> TuShare requires the `TUSHARE_TOKEN` environment variable. Obtain a token from the TuShare website and export it before running the script.

## 2. Quick Start (akshare default)

```bash
python unified_backtest_framework.py run   --strategy turning_point   --symbols 600519.SH 000001.SZ   --start 2020-01-01   --end 2024-01-01   --benchmark 000300.SH   --out_dir reports_demo
```

This command:
- Downloads daily prices for the provided symbols.
- Runs the turning-point strategy with default parameters.
- Compares performance against the CSI 300 index.
- Writes NAV series and summary metrics to `reports_demo/`.

## 3. Selecting Data Providers

| Provider  | Flag        | Requirements                           |
|-----------|-------------|----------------------------------------|
| Akshare   | `akshare`   | `pip install akshare`                   |
| yfinance  | `yfinance`  | `pip install yfinance`                  |
| TuShare   | `tushare`   | `pip install tushare`, `TUSHARE_TOKEN` |

Specify providers via `--source` and optionally `--benchmark_source` if the benchmark should come from a different feed.

Example using yfinance:
```bash
python unified_backtest_framework.py run   --strategy ema   --symbols AAPL   --start 2018-01-01   --end 2023-12-31   --source yfinance   --benchmark ^GSPC   --benchmark_source yfinance
```

## 4. Strategy Catalogue

Run `python unified_backtest_framework.py list` to see available strategies. Out of the box the framework bundles:

- `turning_point` — multi-symbol intent engine with Pareto analysis support.
- `ema` — EMA cross-over (single asset).
- `macd` — MACD signal line cross-over.
- `bollinger` — Bollinger band channel reversals.
- `rsi` — RSI threshold entries.

Each strategy includes sensible defaults and a grid spec used for optimisation.

## 5. Grid Search

Run a parameter sweep via:
```bash
python unified_backtest_framework.py grid   --strategy macd   --symbols 600519.SH   --start 2019-01-01   --end 2024-01-01   --benchmark 000300.SH   --out_csv reports_macd/grid_results.csv   --workers 4
```

Pass a custom grid if required:
```bash
python unified_backtest_framework.py grid   --strategy ema   --symbols 000001.SZ   --start 2021-01-01   --end 2024-01-01   --grid '{"period": [10, 20, 50, 100]}'
```

## 6. Automated Pipeline

The `auto` sub-command performs:
1. Grid search for all selected strategies.
2. CSV/PNG exports for each heatmap (if applicable).
3. Pareto frontier calculation.
4. Top-N replays to generate comparative NAV plots.

Example:
```bash
python unified_backtest_framework.py auto   --symbols 600519.SH 000333.SZ   --start 2018-01-01   --end 2024-01-01   --benchmark 000300.SS   --top_n 3   --out_dir reports_auto_demo \
  --workers 4
```

Output structure under `reports_auto_demo/`:
- `opt_<strategy>.csv` — Raw grid search metrics.
- `heat_<strategy>.png` — Visual heatmaps (strategy dependent).
- `opt_all.csv` — Aggregated optimisation results.
- `pareto_front.csv` — Non-dominated configurations.
- `topN_navs.csv` / `topN_navs.png` — Replay of the Pareto leaders.

## 7. Saving Results

- `--out_dir` controls where NAV curves, comparisons, and the JSON console summary are written for `run`.
- `--out_csv` (grid) stores tabular results.
- `--cache_dir` defines where raw downloads are cached. Reuse the same folder to avoid repeated downloads.

## 8. Extending the Framework

1. **Create a Backtrader strategy** in `unified_backtest_framework.py` or an imported module.
2. **Provide a coercer** that cleans user parameters.
3. **Register a `StrategyModule`** in the `STRATEGY_REGISTRY` list with:
   - Unique `name`
   - Description
   - Strategy class
   - Default parameters and grid definition
4. Optional: override `multi_symbol` or supply custom pre/post-processing.

New strategies automatically become available in the CLI once registered.

## 9. Troubleshooting

- Missing dependency errors indicate the provider’s package is not installed.
- Empty data frames usually mean the symbol is not supported by the provider (use provider-specific tickers).
- TuShare authentication problems are resolved by re-exporting `TUSHARE_TOKEN`.
- Use `--cache_dir` to isolate data per experiment and delete it for a clean re-download.

## 10. Further Ideas

- Add new providers by subclassing `DataProvider` and updating `_PROVIDER_FACTORIES`.
- Wrap the engine in a higher-level API (e.g. FastAPI) for remote execution.
- Integrate custom analyzers by extending `_execute_strategy`.

Happy backtesting!

Tip: Use --workers to parallelise grid search/backtests (default 1).
