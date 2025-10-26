# Modular Backtest Framework - Usage Guide

## 🎯 Quick Start

The framework has been modularized into clean, reusable components. Here's how to use them:

## 📦 Installation

```bash
pip install backtrader pandas numpy akshare yfinance tushare
```

## 🚀 Basic Usage

### 1. Run a Single Backtest

```python
from src.backtest.engine import BacktestEngine

# Initialize engine
engine = BacktestEngine()

# Run strategy
result = engine.run_strategy(
    strategy="ema",              # Strategy name
    symbols=["600519.SH"],       # Stock symbols
    start="2023-01-01",          # Start date
    end="2023-12-31",            # End date
    params={"period": 20},       # Strategy parameters (optional)
    cash=100000,                 # Initial cash
    commission=0.001,            # Commission rate
    benchmark="000300.SH"        # Benchmark index (optional)
)

# Access results
print(f"Cumulative Return: {result['cum_return']:.2%}")
print(f"Sharpe Ratio: {result['sharpe']:.2f}")
print(f"Max Drawdown: {result['mdd']:.2%}")
print(f"Win Rate: {result['win_rate']:.2%}")
```

### 2. Grid Search Optimization

```python
# Define parameter grid
grid = {
    "period": [10, 15, 20, 25, 30],
    "devfactor": [1.5, 2.0, 2.5]
}

# Run grid search (with parallel processing)
results_df = engine.grid_search(
    strategy="bollinger",
    grid=grid,
    symbols=["600519.SH", "000001.SZ"],
    start="2023-01-01",
    end="2023-12-31",
    max_workers=4  # Use 4 CPU cores
)

# Find best parameters
best = results_df.sort_values("sharpe", ascending=False).iloc[0]
print(f"Best params: period={best['period']}, devfactor={best['devfactor']}")
print(f"Sharpe: {best['sharpe']:.2f}")
```

### 3. Custom Data Provider

```python
from src.data_sources.providers import get_provider

# Use AKShare (default, free)
provider = get_provider("akshare")
data = provider.get_data("600519.SH", "2023-01-01", "2023-12-31")

# Or use YFinance (global markets)
provider = get_provider("yfinance")
data = provider.get_data("AAPL", "2023-01-01", "2023-12-31")

# Or use TuShare (requires token)
provider = get_provider("tushare", token="YOUR_TOKEN")
data = provider.get_data("600519.SH", "2023-01-01", "2023-12-31")
```

### 4. Access Strategy Registry

```python
from src.backtest.strategy_modules import STRATEGY_REGISTRY

# List all available strategies
print("Available strategies:", list(STRATEGY_REGISTRY.keys()))

# Get strategy info
module = STRATEGY_REGISTRY["ema"]
print(f"Strategy: {module.name}")
print(f"Description: {module.description}")
print(f"Parameters: {module.param_names}")
print(f"Defaults: {module.defaults}")
```

## 📊 Available Strategies

| Strategy | Description | Key Parameters |
|----------|-------------|----------------|
| `ema` | Exponential Moving Average | `period` |
| `macd` | MACD Crossover | `fast`, `slow`, `signal` |
| `bollinger` | Bollinger Bands | `period`, `devfactor` |
| `rsi` | RSI Overbought/Oversold | `period`, `upper`, `lower` |
| `turning_point` | Multi-symbol Turning Point | `topn`, `gap`, `reversal` |
| `keltner` | Keltner Channel | `ema_period`, `atr_period` |
| `zscore` | Z-Score Mean Reversion | `period`, `z_entry` |
| `donchian` | Donchian Channel | `upper`, `lower` |
| `triple_ma` | Triple Moving Average | `fast`, `mid`, `slow` |
| `adx_trend` | ADX Trend Following | `adx_period`, `adx_th` |

## 🔧 Advanced Usage

### Multi-Symbol Strategy

```python
# Turning point strategy works with multiple symbols
result = engine.run_strategy(
    strategy="turning_point",
    symbols=["600519.SH", "600036.SH", "601318.SH"],
    start="2023-01-01",
    end="2023-12-31",
    params={
        "topn": 2,           # Hold top 2 stocks
        "gap": 0.015,        # Gap threshold 1.5%
        "reversal": 0.003,   # Reversal threshold 0.3%
        "vol_surge": 1.3     # Volume surge 1.3x
    }
)
```

### With Plotting

```python
result = engine.run_strategy(
    strategy="ema",
    symbols=["600519.SH"],
    start="2023-01-01",
    end="2023-12-31",
    enable_plot=True,  # Enable plotting
    out_dir="./results"  # Save to directory
)

# Charts will be saved to ./results/
```

### Custom Cache Directory

```python
# Use custom cache directory
engine = BacktestEngine(
    cache_dir="./my_cache",
    data_provider="yfinance"
)
```

## 📈 Metrics Explained

| Metric | Description | Good Value |
|--------|-------------|------------|
| `cum_return` | Cumulative return | > 0 |
| `sharpe` | Sharpe ratio | > 1.0 |
| `sortino` | Sortino ratio | > 1.5 |
| `calmar` | Calmar ratio | > 0.5 |
| `mdd` | Maximum drawdown | < 20% |
| `win_rate` | Win rate | > 50% |
| `profit_factor` | Profit factor | > 1.5 |
| `payoff_ratio` | Avg win / avg loss | > 1.0 |
| `expectancy` | Expected profit per trade | > 0 |
| `trades` | Number of trades | > 10 |
| `exposure_ratio` | Time in market | 0-1 |

## 🎨 Code Examples

### Example 1: Compare Strategies

```python
strategies = ["ema", "macd", "bollinger", "rsi"]
results = []

for strategy in strategies:
    result = engine.run_strategy(
        strategy=strategy,
        symbols=["600519.SH"],
        start="2023-01-01",
        end="2023-12-31"
    )
    results.append({
        "strategy": strategy,
        "sharpe": result["sharpe"],
        "return": result["cum_return"],
        "mdd": result["mdd"]
    })

import pandas as pd
df = pd.DataFrame(results)
print(df.sort_values("sharpe", ascending=False))
```

### Example 2: Portfolio Optimization

```python
symbols = ["600519.SH", "000333.SZ", "600036.SH"]

# Optimize each symbol separately
for symbol in symbols:
    grid = {"period": range(10, 31, 5)}
    results = engine.grid_search(
        strategy="ema",
        grid=grid,
        symbols=[symbol],
        start="2023-01-01",
        end="2023-12-31"
    )
    best = results.loc[results["sharpe"].idxmax()]
    print(f"{symbol}: best period = {best['period']}, sharpe = {best['sharpe']:.2f}")
```

### Example 3: Walk-Forward Analysis

```python
periods = [
    ("2023-01-01", "2023-06-30"),  # Train
    ("2023-07-01", "2023-12-31")   # Test
]

train_start, train_end = periods[0]
test_start, test_end = periods[1]

# Train (optimize)
grid = {"period": [10, 15, 20, 25, 30]}
train_results = engine.grid_search(
    strategy="ema",
    grid=grid,
    symbols=["600519.SH"],
    start=train_start,
    end=train_end
)
best_period = train_results.loc[train_results["sharpe"].idxmax(), "period"]

# Test (validate)
test_result = engine.run_strategy(
    strategy="ema",
    symbols=["600519.SH"],
    start=test_start,
    end=test_end,
    params={"period": best_period}
)
print(f"Out-of-sample Sharpe: {test_result['sharpe']:.2f}")
```

## 🔗 Integration with Original Framework

The new modular system is compatible with the original `unified_backtest_framework.py`:

```bash
# Original CLI still works
python unified_backtest_framework.py run --strategy ema --symbols 600519.SH --plot

# But you can also use the new modules directly
```

## 📚 Module Reference

### `src.data_sources.providers`
- `get_provider(name, **kwargs)` - Get data provider instance
- `DataProvider` - Abstract base class
- `AkshareProvider` - AKShare implementation
- `YFinanceProvider` - YFinance implementation
- `TuShareProvider` - TuShare implementation

### `src.backtest.engine`
- `BacktestEngine` - Main backtest engine
  - `run_strategy()` - Run single backtest
  - `grid_search()` - Parameter optimization
  - `_load_data()` - Load market data
  - `_load_benchmark()` - Load benchmark

### `src.backtest.strategy_modules`
- `STRATEGY_REGISTRY` - All available strategies
- `StrategyModule` - Strategy metadata
- `TurningPointBT` - Turning point strategy
- `GenericPandasData` - Backtrader data feed
- `IntentLogger` - Trade intent analyzer

## 🐛 Troubleshooting

### Import Error
```python
# Make sure you're in the project root
import sys
sys.path.insert(0, '/path/to/stock')

from src.backtest.engine import BacktestEngine
```

### Data Loading Error
```python
# Check symbol format
# Chinese stocks: "600519.SH" or "000001.SZ"
# US stocks: "AAPL", "MSFT", etc.
```

### No Trades Generated
```python
# Check if parameters are too restrictive
# Try default parameters first
result = engine.run_strategy(
    strategy="ema",
    symbols=["600519.SH"],
    start="2023-01-01",
    end="2023-12-31"
    # No custom params - use defaults
)
```

## 📞 Support

- Documentation: `docs/` folder
- Examples: `test/` folder
- Issues: Check error messages and logs

## 🎉 Happy Backtesting!

The modular framework provides:
- ✅ Clean, maintainable code
- ✅ Easy extensibility
- ✅ High performance
- ✅ Type safety
- ✅ Comprehensive metrics

Start with simple examples and gradually explore advanced features.

---

**Version**: V2.5.0-alpha
**Status**: Phase 1 Complete
**Last Updated**: 2024
