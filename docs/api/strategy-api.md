# Strategy API

Strategies are registered under the strategy registry used by the CLI, API, and admission workflows.

## Basic workflow

1. Pick an existing strategy from the registry.
2. Run a backtest with fixed parameters.
3. Register a historical baseline.
4. Run admission before portfolio, paper, or live stages.

## References

- [Strategy reference](../STRATEGY_REFERENCE.md)
- [Strategy admission](../guides/strategy-admission.md)
- [API reference](../API_REFERENCE.md)