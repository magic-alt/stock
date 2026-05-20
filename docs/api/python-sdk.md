# Python SDK

The repository is organized as importable Python modules under `src/`. The current public package metadata is defined in `pyproject.toml` with Python 3.10+ support.

## Common imports

```python
from src.backtest.engine import BacktestEngine
from src.backtest.admission import evaluate_admission
from src.backtest.admission_gates import require_strategy_stage
```

## Scaffold helper

New strategy and factor files can be generated with:

```bash
python -m src.cli.scaffold strategy my_strategy --template trend_following
```

See [API reference](../API_REFERENCE.md) and [Strategy reference](../STRATEGY_REFERENCE.md) for available modules and strategy names.