# Backtesting

The CLI supports single strategy runs, grid search, automated strategy search, portfolio combinations, and baseline/admission workflows.

## Single strategy

```bash
python unified_backtest_framework.py run \
  --strategy macd \
  --symbols 600519.SH \
  --start 2023-01-01 --end 2024-12-31
```

## Strategy list

```bash
python unified_backtest_framework.py list
```

## Outputs

Backtest artifacts are written to `report/` by default, including run snapshots, data quality reports, metrics JSON, Markdown summaries, and chart assets when plotting is enabled.

## Related references

- [API reference](../API_REFERENCE.md)
- [Strategy reference](../STRATEGY_REFERENCE.md)
- [Performance benchmark spec](../PERFORMANCE_BENCHMARK_SPEC.md)