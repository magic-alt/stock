"""
API Reference Documentation

This module provides comprehensive documentation for the Quantitative Trading Platform API.
All public interfaces, classes, and functions are documented here.

V3.1.0: Initial release - comprehensive API documentation

Table of Contents:
1. Core Modules
2. Data Sources
3. Strategies
4. Backtest Engine
5. Risk Management
6. Utilities

Quick Start:
    >>> from src.core import BacktestEngine, STRATEGY_REGISTRY
    >>> from src.data_sources.providers import get_provider
    >>> 
    >>> # Run a simple backtest
    >>> engine = BacktestEngine(source="akshare")
    >>> result = engine.run_strategy("macd", ["600519.SH"], "2024-01-01", "2024-12-31")
"""

# =============================================================================
# API REFERENCE
# =============================================================================

API_OVERVIEW = """
# Quantitative Trading Platform API Reference

## Version: V3.1.0
## Date: 2026-01-11

---

## 1. Core Modules

### 1.1 BacktestEngine (`src/backtest/engine.py`)

Main entry point for running backtests.

```python
from src.backtest.engine import BacktestEngine

class BacktestEngine:
    '''
    Core backtest engine supporting multiple strategies and data sources.
    
    Parameters
    ----------
    source : str, default "akshare"
        Data source provider. Options: "akshare", "yfinance", "tushare"
    benchmark_source : str, optional
        Data source for benchmark. Defaults to same as source.
    cache_dir : str, default "./cache"
        Directory for data cache.
    
    Methods
    -------
    run_strategy(strategy, symbols, start, end, **kwargs)
        Run a single strategy backtest.
    grid_search(strategy, grid, symbols, start, end, **kwargs)
        Run grid search optimization.
    auto_pipeline(symbols, start, end, **kwargs)
        Run full automated pipeline with multiple strategies.
    
    Examples
    --------
    >>> engine = BacktestEngine(source="akshare")
    >>> metrics = engine.run_strategy(
    ...     "macd",
    ...     symbols=["600519.SH"],
    ...     start="2024-01-01",
    ...     end="2024-12-31",
    ...     cash=100000,
    ...     commission=0.0001,
    ... )
    >>> print(f"Total Return: {metrics['total_return']:.2%}")
    '''
```

#### run_strategy()

```python
def run_strategy(
    self,
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
) -> Dict[str, Any]:
    '''
    Run a single strategy backtest.
    
    Parameters
    ----------
    strategy : str
        Strategy name (must be in STRATEGY_REGISTRY).
    symbols : List[str]
        List of stock symbols (e.g., ["600519.SH", "000858.SZ"]).
    start : str
        Start date in YYYY-MM-DD format.
    end : str
        End date in YYYY-MM-DD format.
    params : Dict[str, Any], optional
        Strategy parameters to override defaults.
    cash : float, default 100000.0
        Initial cash amount.
    commission : float, default 0.0001
        Commission rate (0.01% = 0.0001).
    slippage : float, default 0.0005
        Slippage rate (0.05% = 0.0005).
    benchmark : str, optional
        Benchmark symbol for comparison.
    adj : str, optional
        Adjustment type: "qfq" (forward), "hfq" (backward), None (raw).
    out_dir : str, optional
        Output directory for reports.
    enable_plot : bool, default False
        Whether to generate visualization.
    fee_plugin : str, optional
        Fee plugin name (e.g., "cn_stock").
    fee_plugin_params : Dict, optional
        Fee plugin parameters.
    
    Returns
    -------
    Dict[str, Any]
        Backtest metrics including:
        - total_return: Total return percentage
        - annual_return: Annualized return
        - sharpe_ratio: Sharpe ratio
        - max_drawdown: Maximum drawdown
        - win_rate: Win rate percentage
        - profit_factor: Profit factor
        - total_trades: Number of trades
        - nav: Net asset value series (pandas.Series)
    
    Raises
    ------
    StrategyNotFoundError
        If strategy is not registered.
    DataNotFoundError
        If no data available for symbols.
    
    Examples
    --------
    >>> metrics = engine.run_strategy(
    ...     "ema_cross",
    ...     symbols=["600519.SH"],
    ...     start="2024-01-01",
    ...     end="2024-12-31",
    ...     params={"fast_period": 10, "slow_period": 30},
    ...     cash=200000,
    ... )
    '''
```

#### grid_search()

```python
def grid_search(
    self,
    strategy: str,
    grid: Dict[str, List[Any]],
    symbols: List[str],
    start: str,
    end: str,
    *,
    cash: float = 100000.0,
    commission: float = 0.0001,
    slippage: float = 0.0005,
    benchmark: Optional[str] = None,
    adj: Optional[str] = None,
    max_workers: int = 1,
) -> pd.DataFrame:
    '''
    Run grid search optimization.
    
    Parameters
    ----------
    strategy : str
        Strategy name.
    grid : Dict[str, List[Any]]
        Parameter grid. Example: {"fast": [5, 10, 20], "slow": [20, 30, 50]}
    symbols : List[str]
        Stock symbols.
    start, end : str
        Date range.
    max_workers : int, default 1
        Number of parallel workers.
    
    Returns
    -------
    pd.DataFrame
        Results with columns: params, total_return, sharpe_ratio, max_drawdown, etc.
    
    Examples
    --------
    >>> df = engine.grid_search(
    ...     "macd",
    ...     grid={"fast": [10, 12, 14], "slow": [26, 30], "signal": [9]},
    ...     symbols=["600519.SH"],
    ...     start="2024-01-01",
    ...     end="2024-12-31",
    ...     max_workers=4,
    ... )
    >>> best = df.loc[df["sharpe_ratio"].idxmax()]
    '''
```

### 1.2 Strategy Registry (`src/backtest/strategy_modules.py`)

```python
from src.backtest.strategy_modules import STRATEGY_REGISTRY, StrategyModule

# List all available strategies
for name, module in STRATEGY_REGISTRY.items():
    print(f"{name}: {module.description}")

# Get strategy module
module = STRATEGY_REGISTRY["macd"]
print(f"Default params: {module.default_params}")
print(f"Grid defaults: {module.grid_defaults}")
```

### 1.3 Data Providers (`src/data_sources/providers.py`)

```python
from src.data_sources.providers import get_provider, PROVIDER_NAMES

class DataProvider:
    '''
    Abstract base class for data providers.
    
    Available Providers
    -------------------
    - AkshareProvider: Free Chinese A-share data
    - YfinanceProvider: Global market data
    - TushareProvider: Professional Chinese data (requires token)
    
    Methods
    -------
    load_stock_daily(symbols, start, end, adj=None)
        Load daily OHLCV data.
    
    Examples
    --------
    >>> provider = get_provider("akshare")
    >>> data = provider.load_stock_daily(
    ...     ["600519.SH"],
    ...     "2024-01-01",
    ...     "2024-12-31",
    ...     adj="hfq"
    ... )
    >>> print(data["600519.SH"].head())
    '''
```

---

## 2. Data Types (`src/core/interfaces.py`)

### 2.1 BarData

```python
from src.core.interfaces import BarData

@dataclass
class BarData:
    '''
    OHLCV bar data container.
    
    Attributes
    ----------
    symbol : str
        Stock symbol.
    timestamp : datetime
        Bar timestamp.
    open : float
        Open price.
    high : float
        High price.
    low : float
        Low price.
    close : float
        Close price.
    volume : float
        Trading volume.
    
    Methods
    -------
    to_series() -> pd.Series
        Convert to pandas Series.
    from_series(symbol, timestamp, series) -> BarData
        Create from pandas Series.
    '''
```

### 2.2 PositionInfo

```python
from src.core.interfaces import PositionInfo

@dataclass
class PositionInfo:
    '''
    Position information.
    
    Attributes
    ----------
    symbol : str
        Symbol.
    size : float
        Position size (positive=long, negative=short).
    avg_price : float
        Average entry price.
    market_value : float
        Current market value.
    unrealized_pnl : float
        Unrealized profit/loss.
    realized_pnl : float
        Realized profit/loss.
    
    Properties
    ----------
    is_long : bool
    is_short : bool
    is_flat : bool
    '''
```

### 2.3 AccountInfo

```python
from src.core.interfaces import AccountInfo

@dataclass
class AccountInfo:
    '''
    Account information.
    
    Attributes
    ----------
    account_id : str
        Account identifier.
    cash : float
        Available cash.
    total_value : float
        Total portfolio value.
    available : float
        Available for trading.
    margin : float
        Used margin.
    unrealized_pnl : float
        Unrealized P/L.
    realized_pnl : float
        Realized P/L.
    '''
```

---

## 3. Exception Handling (`src/core/exceptions.py`)

### 3.1 Exception Hierarchy

```python
from src.core.exceptions import (
    QuantBaseError,      # Base class
    ConfigurationError,  # Config issues
    DataError,          # Data issues
    DataNotFoundError,  # Missing data
    StrategyError,      # Strategy issues
    OrderError,         # Order issues
    GatewayError,       # Gateway issues
    RiskError,          # Risk limit violations
    BacktestError,      # Backtest issues
)

# Example usage
try:
    result = engine.run_strategy("unknown_strategy", ...)
except StrategyNotFoundError as e:
    print(f"Strategy error: {e.error_code} - {e.message}")
except DataError as e:
    print(f"Data error: {e}")
```

### 3.2 Error Handler

```python
from src.core.error_handler import handle_errors, ErrorHandler

# Decorator usage
@handle_errors(default_return=[], reraise=False)
def get_data():
    '''Will return [] on error instead of raising.'''
    ...

# Context manager usage
with ErrorHandler(operation="data_load", reraise=True):
    data = load_data()

# Get error statistics
stats = ErrorHandler.get_statistics()
```

---

## 4. Risk Management (`src/core/risk_manager_v2.py`)

```python
from src.core.risk_manager_v2 import RiskManagerV2

class RiskManagerV2:
    '''
    Multi-level risk management system.
    
    Features
    --------
    - Account-level risk limits
    - Strategy-level limits
    - Order-level validation
    - Position limits
    - Drawdown control
    
    Parameters
    ----------
    max_position_pct : float
        Maximum position as % of portfolio.
    max_drawdown : float
        Maximum allowed drawdown.
    max_order_value : float
        Maximum single order value.
    
    Methods
    -------
    check_order(order) -> Tuple[bool, str]
        Validate order against risk rules.
    check_position(symbol, size) -> bool
        Check position limits.
    update_account(account_info)
        Update account state.
    '''
```

---

## 5. CLI Reference

### 5.1 Basic Commands

```bash
# Run single backtest
python unified_backtest_framework.py run \\
    --strategy macd \\
    --symbols 600519.SH \\
    --start 2024-01-01 \\
    --end 2024-12-31 \\
    --cash 100000 \\
    --plot

# Grid search optimization
python unified_backtest_framework.py grid \\
    --strategy macd \\
    --symbols 600519.SH \\
    --start 2024-01-01 \\
    --end 2024-12-31 \\
    --grid '{"fast":[10,12],"slow":[26,30]}' \\
    --workers 4

# Auto pipeline (multi-strategy)
python unified_backtest_framework.py auto \\
    --symbols 600519.SH 000858.SZ \\
    --start 2024-01-01 \\
    --end 2024-12-31 \\
    --strategies macd ema_cross rsi \\
    --workers 4

# List available strategies
python unified_backtest_framework.py list

# Portfolio combination
python unified_backtest_framework.py combo \\
    --navs nav1.csv nav2.csv \\
    --objective sharpe \\
    --step 0.1
```

### 5.2 CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| --strategy | Strategy name | turning_point |
| --symbols | Stock symbols (space-separated) | Required |
| --start | Start date (YYYY-MM-DD) | Required |
| --end | End date (YYYY-MM-DD) | Required |
| --source | Data source | akshare |
| --cash | Initial capital | 200000 |
| --commission | Commission rate | 0.0001 |
| --slippage | Slippage rate | 0.0005 |
| --benchmark | Benchmark symbol | None |
| --plot | Generate charts | False |
| --out_dir | Output directory | None |
| --workers | Parallel workers | 1 |

---

## 6. Available Strategies

| Strategy | Description | Type |
|----------|-------------|------|
| macd | MACD Signal Strategy | Trend |
| ema_cross | EMA Crossover | Trend |
| sma_cross | SMA Crossover | Trend |
| bollinger | Bollinger Bands | Mean Reversion |
| rsi | RSI Overbought/Oversold | Momentum |
| adx_trend | ADX Trend Following | Trend |
| donchian | Donchian Channel Breakout | Breakout |
| keltner | Keltner Channel | Mean Reversion |
| triple_ma | Triple Moving Average | Trend |
| zscore | Z-Score Mean Reversion | Mean Reversion |
| risk_parity | Risk Parity Portfolio | Portfolio |
| turning_point | Turning Point Detection | Pattern |
| ml_walk | ML Walk-Forward | Machine Learning |

---

## 7. Configuration (`config.yaml`)

```yaml
# System Configuration
system:
  log_level: INFO
  log_format: json  # json or text
  cache_dir: ./cache
  report_dir: ./report

# Data Source Configuration
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

## 8. Performance Metrics

| Metric | Description | Formula |
|--------|-------------|---------|
| total_return | Total return | (Final - Initial) / Initial |
| annual_return | Annualized return | (1 + total_return)^(252/days) - 1 |
| sharpe_ratio | Risk-adjusted return | mean(returns) / std(returns) * sqrt(252) |
| max_drawdown | Maximum drawdown | max(peak - trough) / peak |
| win_rate | Win rate | wins / total_trades |
| profit_factor | Profit factor | gross_profit / gross_loss |
| calmar_ratio | Calmar ratio | annual_return / max_drawdown |

---

## 9. Error Codes

| Code | Description |
|------|-------------|
| CONFIG_ERROR | Configuration error |
| DATA_ERROR | Data-related error |
| DATA_NOT_FOUND | Data not found |
| STRATEGY_ERROR | Strategy error |
| STRATEGY_NOT_FOUND | Strategy not registered |
| ORDER_ERROR | Order error |
| ORDER_REJECTED | Order rejected |
| GATEWAY_ERROR | Gateway error |
| RISK_LIMIT_EXCEEDED | Risk limit exceeded |
| BACKTEST_ERROR | Backtest error |
"""


def print_api_docs():
    """Print API documentation to console."""
    print(API_OVERVIEW)


if __name__ == "__main__":
    print_api_docs()
