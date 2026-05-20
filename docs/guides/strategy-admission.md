# Strategy Admission

Strategy admission turns one-off backtests into a repeatable review workflow. A strategy is evaluated against fixed historical regimes, baseline drift, data quality checks, and parameter signatures before it is allowed into paper trading, portfolio allocation, or live preflight.

## Register a baseline

```bash
python unified_backtest_framework.py baseline --strategy macd \
  --params '{"fast": 12, "slow": 26, "signal": 9}' \
  --register-strategy-baseline --baseline-alias prod \
  --regimes bull bear range high-vol
```

## Run admission

```bash
python unified_backtest_framework.py admission --strategy macd \
  --params '{"fast": 12, "slow": 26, "signal": 9}' \
  --profile institutional --baseline-alias prod \
  --regimes bull bear range high-vol
```

## Gate sequence

The current gate sequence is:

```text
research -> baseline_registered -> admission_passed -> paper_validated -> live_candidate -> production
```

The detailed workflow and artifact layout are documented in [Historical Baseline and Strategy Admission](../STRATEGY_ADMISSION_WORKFLOW.md).