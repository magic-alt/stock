# API Reference Documentation

**Version**: V3.1.0  
**Date**: 2026-01-11  
**Status**: 🟢 Production Ready

---

## Table of Contents

- [Quick Start](#quick-start)
- [Core Modules](#core-modules)
  - [BacktestEngine](#backtestengine)
  - [Strategy Registry](#strategy-registry)
  - [Data Providers](#data-providers)
- [Data Types](#data-types)
- [Exception Handling](#exception-handling)
- [Risk Management](#risk-management)
- [CLI Reference](#cli-reference)
- [Available Strategies](#available-strategies)
- [Performance Metrics](#performance-metrics)
- [Error Codes](#error-codes)

---

## Quick Start

```python
from src.backtest.engine import BacktestEngine
from src.backtest.strategy_modules import STRATEGY_REGISTRY

# Initialize engine
engine = BacktestEngine(source="akshare")

# Run a simple backtest
result = engine.run_strategy(
    "macd",
    symbols=["600519.SH"],
    start="2024-01-01",
    end="2024-12-31",
    cash=100000,
    commission=0.0001,
)

print(f"Total Return: {result['total_return']:.2%}")
print(f"Sharpe Ratio: {result['sharpe_ratio']:.2f}")
```

---

## Core Modules

### BacktestEngine

**Location**: `src/backtest/engine.py`

Main entry point for running backtests.

#### Constructor

```python
BacktestEngine(
    source: str = "akshare",
    benchmark_source: str = None,
    cache_dir: str = "./cache"
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source` | str | "akshare" | Data source provider |
| `benchmark_source` | str | None | Benchmark data source |
| `cache_dir` | str | "./cache" | Cache directory |

#### Methods

##### run_strategy()

Run a single strategy backtest.

```python
def run_strategy(
    strategy: str,
    symbols: List[str],
    start: str,
    end: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    cash: float = 100000.0,
    commission: float = 0.0001,
    slippage: float = 0.0005,
    benchmark: Optional[str] = None,
    adj: Optional[str] = None,
    out_dir: Optional[str] = None,
    enable_plot: bool = False,
    fee_plugin: Optional[str] = None,
    fee_plugin_params: Optional[Dict] = None,
) -> Dict[str, Any]
```

**Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `strategy` | str | Required | Strategy name from registry |
| `symbols` | List[str] | Required | Stock symbols |
| `start` | str | Required | Start date (YYYY-MM-DD) |
| `end` | str | Required | End date (YYYY-MM-DD) |
| `params` | Dict | None | Strategy parameters |
| `cash` | float | 100000 | Initial capital |
| `commission` | float | 0.0001 | Commission rate |
| `slippage` | float | 0.0005 | Slippage rate |
| `benchmark` | str | None | Benchmark symbol |
| `adj` | str | None | Adjustment type |
| `enable_plot` | bool | False | Generate charts |

**Returns**: `Dict[str, Any]` with metrics:
- `total_return`: Total return percentage
- `annual_return`: Annualized return
- `sharpe_ratio`: Sharpe ratio
- `max_drawdown`: Maximum drawdown
- `win_rate`: Win rate
- `total_trades`: Number of trades
- `nav`: Net asset value series

**Example**:

```python
metrics = engine.run_strategy(
    "ema_cross",
    symbols=["600519.SH"],
    start="2024-01-01",
    end="2024-12-31",
    params={"fast_period": 10, "slow_period": 30},
    cash=200000,
    enable_plot=True,
)
```

##### grid_search()

Run parameter grid search optimization.

```python
def grid_search(
    strategy: str,
    grid: Dict[str, List[Any]],
    symbols: List[str],
    start: str,
    end: str,
    *,
    max_workers: int = 1,
) -> pd.DataFrame
```

**Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `strategy` | str | Required | Strategy name |
| `grid` | Dict | Required | Parameter grid |
| `symbols` | List[str] | Required | Stock symbols |
| `max_workers` | int | 1 | Parallel workers |

**Returns**: `pd.DataFrame` with results for each parameter combination

**Example**:

```python
df = engine.grid_search(
    "macd",
    grid={"fast": [10, 12, 14], "slow": [26, 30], "signal": [9]},
    symbols=["600519.SH"],
    start="2024-01-01",
    end="2024-12-31",
    max_workers=4,
)
best = df.loc[df["sharpe_ratio"].idxmax()]
```

##### auto_pipeline()

Run full automated pipeline with multiple strategies.

```python
def auto_pipeline(
    symbols: List[str],
    start: str,
    end: str,
    *,
    strategies: Optional[List[str]] = None,
    benchmark: str = "000300.SH",
    top_n: int = 5,
    workers: int = 1,
    out_dir: str = "./reports_auto",
) -> None
```

---

### Strategy Registry

**Location**: `src/backtest/strategy_modules.py`

```python
from src.backtest.strategy_modules import STRATEGY_REGISTRY, StrategyModule

# List all strategies
for name, module in STRATEGY_REGISTRY.items():
    print(f"{name}: {module.description}")

# Get strategy info
module = STRATEGY_REGISTRY["macd"]
print(f"Default params: {module.default_params}")
print(f"Grid defaults: {module.grid_defaults}")
```

---

### Data Providers

**Location**: `src/data_sources/providers.py`

```python
from src.data_sources.providers import get_provider, PROVIDER_NAMES

# Available providers
print(PROVIDER_NAMES)  # ['akshare', 'yfinance', 'tushare']

# Get provider
provider = get_provider("akshare")

# Load data
data = provider.load_stock_daily(
    ["600519.SH"],
    "2024-01-01",
    "2024-12-31",
    adj="hfq"  # "qfq", "hfq", or None
)
```

| Provider | Market | Requirements | Features |
|----------|--------|--------------|----------|
| AkshareProvider | China A-share | Free | Default, no token |
| YfinanceProvider | Global | Free | US/HK/Global |
| TushareProvider | China A-share | Token | Professional |

---

## Data Types

**Location**: `src/core/interfaces.py`

### BarData

```python
@dataclass
class BarData:
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
```

### PositionInfo

```python
@dataclass
class PositionInfo:
    symbol: str
    size: float = 0.0  # Positive=long, negative=short
    avg_price: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
```

### AccountInfo

```python
@dataclass
class AccountInfo:
    account_id: str = "default"
    cash: float = 100000.0
    total_value: float = 100000.0
    available: float = 100000.0
    margin: float = 0.0
```

---

## Exception Handling

**Location**: `src/core/exceptions.py`, `src/core/error_handler.py`

### Exception Hierarchy

```
QuantBaseError (base)
├── ConfigurationError
├── DataError
│   ├── DataProviderError
│   ├── DataValidationError
│   └── DataNotFoundError
├── StrategyError
│   ├── StrategyNotFoundError
│   └── StrategyExecutionError
├── OrderError
│   ├── OrderValidationError
│   └── InsufficientFundsError
├── GatewayError
├── RiskError
│   └── RiskLimitExceeded
└── BacktestError
```

### Usage Examples

```python
from src.core.exceptions import (
    DataNotFoundError,
    StrategyNotFoundError,
    QuantBaseError,
)
from src.core.error_handler import handle_errors, ErrorHandler

# Decorator usage
@handle_errors(default_return=[], reraise=False)
def get_data():
    """Returns [] on error instead of raising."""
    ...

# Context manager usage
with ErrorHandler(operation="data_load", reraise=True):
    data = load_data()

# Exception handling
try:
    result = engine.run_strategy("unknown", ...)
except StrategyNotFoundError as e:
    print(f"Error: {e.error_code} - {e.message}")
except DataError as e:
    print(f"Data error: {e}")

# Get error statistics
stats = ErrorHandler.get_statistics()
```

---

## Risk Management

**Location**: `src/core/risk_manager_v2.py`

```python
from src.core.risk_manager_v2 import RiskManagerV2

# Risk manager with custom limits
risk_mgr = RiskManagerV2(
    max_position_pct=0.25,  # Max 25% in single position
    max_drawdown=0.20,      # Max 20% drawdown
    max_order_value=50000,  # Max order value
)

# Check order
is_valid, reason = risk_mgr.check_order(order)
if not is_valid:
    print(f"Order rejected: {reason}")
```

---

## CLI Reference

### Commands

```bash
# Run single backtest
python unified_backtest_framework.py run \
    --strategy macd \
    --symbols 600519.SH \
    --start 2024-01-01 \
    --end 2024-12-31 \
    --cash 100000 \
    --plot

# Grid search
python unified_backtest_framework.py grid \
    --strategy macd \
    --symbols 600519.SH \
    --grid '{"fast":[10,12],"slow":[26,30]}' \
    --workers 4

# Auto pipeline
python unified_backtest_framework.py auto \
    --symbols 600519.SH 000858.SZ \
    --strategies macd ema_cross rsi \
    --workers 4

# List strategies
python unified_backtest_framework.py list

# Portfolio combination
python unified_backtest_framework.py combo \
    --navs nav1.csv nav2.csv \
    --objective sharpe
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--strategy` | Strategy name | turning_point |
| `--symbols` | Stock symbols | Required |
| `--start` | Start date | Required |
| `--end` | End date | Required |
| `--source` | Data source | akshare |
| `--cash` | Initial capital | 200000 |
| `--commission` | Commission rate | 0.0001 |
| `--slippage` | Slippage rate | 0.0005 |
| `--benchmark` | Benchmark | None |
| `--plot` | Generate charts | False |
| `--workers` | Parallel workers | 1 |

---

## Available Strategies

| Strategy | Type | Description |
|----------|------|-------------|
| `macd` | Trend | MACD Signal Strategy |
| `ema_cross` | Trend | EMA Crossover |
| `sma_cross` | Trend | SMA Crossover |
| `bollinger` | Mean Reversion | Bollinger Bands |
| `rsi` | Momentum | RSI Overbought/Oversold |
| `adx_trend` | Trend | ADX Trend Following |
| `donchian` | Breakout | Donchian Channel |
| `keltner` | Mean Reversion | Keltner Channel |
| `triple_ma` | Trend | Triple Moving Average |
| `zscore` | Mean Reversion | Z-Score Strategy |
| `risk_parity` | Portfolio | Risk Parity |
| `turning_point` | Pattern | Turning Point Detection |
| `ml_walk` | ML | Walk-Forward ML |

---

## Performance Metrics

| Metric | Description | Formula |
|--------|-------------|---------|
| `total_return` | Total return | (Final - Initial) / Initial |
| `annual_return` | Annualized return | (1 + total_return)^(252/days) - 1 |
| `sharpe_ratio` | Risk-adjusted return | μ / σ × √252 |
| `max_drawdown` | Maximum drawdown | max(peak - trough) / peak |
| `win_rate` | Win rate | wins / total_trades |
| `profit_factor` | Profit factor | gross_profit / gross_loss |
| `calmar_ratio` | Calmar ratio | annual_return / max_drawdown |
| `sortino_ratio` | Downside risk-adjusted | μ / σ_down × √252 |

---

## Error Codes

| Code | Description |
|------|-------------|
| `CONFIG_ERROR` | Configuration error |
| `CONFIG_MISSING` | Missing configuration |
| `CONFIG_INVALID` | Invalid configuration |
| `DATA_ERROR` | Data-related error |
| `DATA_NOT_FOUND` | Data not found |
| `DATA_VALIDATION_ERROR` | Data validation failed |
| `STRATEGY_ERROR` | Strategy error |
| `STRATEGY_NOT_FOUND` | Strategy not registered |
| `STRATEGY_INIT_ERROR` | Strategy initialization failed |
| `STRATEGY_EXEC_ERROR` | Strategy execution failed |
| `ORDER_ERROR` | Order error |
| `ORDER_REJECTED` | Order rejected |
| `INSUFFICIENT_FUNDS` | Insufficient funds |
| `GATEWAY_ERROR` | Gateway error |
| `GATEWAY_CONNECTION_ERROR` | Connection failed |
| `GATEWAY_TIMEOUT` | Operation timeout |
| `RISK_LIMIT_EXCEEDED` | Risk limit exceeded |
| `POSITION_LIMIT_EXCEEDED` | Position limit exceeded |
| `BACKTEST_ERROR` | Backtest error |
| `BACKTEST_NO_TRADES` | No trades generated |

---

## Configuration File

**File**: `config.yaml`

```yaml
# System Configuration
system:
  log_level: INFO
  log_format: json
  cache_dir: ./cache
  report_dir: ./report

# Data Configuration
data:
  default_provider: akshare
  cache_enabled: true
  cache_days: 30

# Backtest Configuration
backtest:
  default_cash: 100000
  default_commission: 0.0001
  default_slippage: 0.0005
  max_workers: 4

# Risk Management
risk:
  max_position_pct: 0.25
  max_drawdown: 0.20
  max_order_value: 50000
```

---

## See Also

- [Deployment Guide](DEPLOYMENT_GUIDE.md)
- [Architecture Review](ARCHITECTURE_REVIEW.md)
- [Quick Start](../QUICK_START_DEPLOYMENT.md)
- [Changelog](../CHANGELOG.md)

---

**Last Updated**: 2026-01-11  
**Maintainer**: Quantitative Trading Team
