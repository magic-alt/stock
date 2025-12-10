"""
Paper Trading Runner V3 - Execute strategies with simulated order matching.

V3.0 重构版本：
- 使用 BaseStrategy 统一策略接口
- 使用 EventEngineContext 桥接策略与执行引擎
- 使用 PaperGatewayV3 (MatchingEngine) 实现订单匹配
- 向后兼容旧的 StrategyTemplate 接口

This module provides the main entry point for running strategies in paper trading mode.
It orchestrates the interaction between:
- BaseStrategy (unified strategy interface)
- EventEngineContext (strategy-gateway bridge)
- PaperGatewayV3 (simulated broker with MatchingEngine)
- EventEngine (message passing)
- Data feeds (historical bars)

Usage (V3 BaseStrategy):
    >>> from src.core.paper_runner_v3 import run_paper_v3
    >>> from src.core.strategy_base import BaseStrategy
    >>> 
    >>> class MyStrategy(BaseStrategy):
    ...     def on_bar(self, symbol: str, bar: BarData) -> None:
    ...         history = self.ctx.history(symbol, 20, "close")
    ...         if bar.close > history.mean():
    ...             self.ctx.buy(symbol, 100)
    >>> 
    >>> result = run_paper_v3(MyStrategy(), data_map, events)

Usage (Legacy StrategyTemplate - backward compatible):
    >>> from src.core.paper_runner_v3 import run_paper_legacy
    >>> result = run_paper_legacy(legacy_strategy, data_map, events)
"""

from __future__ import annotations

from typing import Dict, Any, Optional, List, Union, TYPE_CHECKING, Callable
import pandas as pd
from datetime import datetime
from abc import ABC

# V3 imports
from src.core.interfaces import BarData, Side, OrderTypeEnum
from src.core.strategy_base import BaseStrategy
from src.core.context import EventEngineContext
from src.core.paper_gateway_v3 import PaperGateway as PaperGatewayV3
from src.core.events import EventEngine
from src.core.logger import get_logger

# Legacy template support removed in V3.1.0
# The StrategyTemplate is deprecated - use BaseStrategy instead
HAS_LEGACY_TEMPLATE = False
StrategyTemplate = None  # type: ignore

logger = get_logger(__name__)


# =============================================================================
# V3 Runner: BaseStrategy + EventEngineContext
# =============================================================================

def run_paper_v3(
    strategy: BaseStrategy,
    data_map: Dict[str, pd.DataFrame],
    events: EventEngine,
    *,
    slippage: float = 0.0,
    initial_cash: float = 200_000.0,
    commission_rate: float = 0.0003,
    on_bar_callback: Optional[Callable[[str, BarData], None]] = None,
) -> Dict[str, Any]:
    """
    V3 Paper trading runner using BaseStrategy and EventEngineContext.
    
    这是推荐的运行方式，使用统一的 BaseStrategy 接口和 Context 模式。
    
    Args:
        strategy: BaseStrategy 实例
        data_map: Dict mapping symbol -> DataFrame with OHLCV data
        events: EventEngine for publishing trade events
        slippage: Slippage factor (e.g., 0.001 = 0.1%)
        initial_cash: Starting capital
        commission_rate: Commission rate (default 0.03%)
        on_bar_callback: Optional callback after each bar processed
    
    Returns:
        Dict with:
        - account: Final account state (cash, equity, positions)
        - nav: pd.Series of daily equity
        - trades: List of filled orders
        - metrics: Basic performance metrics
        
    Example:
        >>> from src.strategies.unified_strategies import UnifiedEMAStrategy
        >>> strategy = UnifiedEMAStrategy(fast_period=5, slow_period=20)
        >>> result = run_paper_v3(strategy, data_map, events)
        >>> print(f"Final equity: {result['account']['equity']:,.2f}")
    """
    logger.info("run_paper_v3.start", 
                symbols=list(data_map.keys()),
                initial_cash=initial_cash,
                slippage=slippage)
    
    # Validate inputs
    if not data_map:
        raise ValueError("data_map cannot be empty")
    
    if not isinstance(strategy, BaseStrategy):
        raise TypeError(f"strategy must be BaseStrategy, got {type(strategy)}")
    
    # Create V3 gateway
    gateway = PaperGatewayV3(
        events=events,
        initial_cash=initial_cash,
        slippage=slippage,
        commission_rate=commission_rate,
    )
    
    # Create context bridge
    ctx = EventEngineContext(gateway=gateway, events=events)
    
    # Track NAV and trades
    nav_records: List[Dict[str, Any]] = []
    trades: List[Dict[str, Any]] = []
    
    # Subscribe to order filled events
    def on_fill(event):
        trade_data = event.data if hasattr(event, 'data') else event
        trades.append(trade_data)
    events.register("order.filled", on_fill)
    
    # Load historical data into context
    ctx.load_data(data_map)
    
    # Strategy lifecycle: Initialize
    strategy.set_context(ctx)
    strategy.on_init()
    strategy.on_start()
    
    logger.debug("strategy.lifecycle", phase="started")
    
    # Build timeline from all data
    all_dates = sorted(set().union(*[set(df.index) for df in data_map.values()]))
    
    # Simulation loop
    account = {"equity": initial_cash}
    
    for dt in all_dates:
        ctx._current_dt = dt  # Update context's current time
        
        # Phase 1: Match pending orders at open price
        for symbol, df in data_map.items():
            if dt in df.index:
                open_price = float(df.loc[dt, "open"])
                gateway.match_orders(symbol, open_price, dt)
        
        # Phase 2: Process bars through strategy
        for symbol, df in data_map.items():
            if dt in df.index:
                row = df.loc[dt]
                bar = BarData(
                    symbol=symbol,
                    datetime=dt if isinstance(dt, datetime) else pd.Timestamp(dt).to_pydatetime(),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row.get("volume", 0)),
                )
                
                # Call strategy bar handler
                strategy.on_bar(symbol, bar)
                
                # Update last price for equity calculation
                gateway.update_price(symbol, float(row["close"]))
                
                # Optional callback
                if on_bar_callback:
                    on_bar_callback(symbol, bar)
        
        # Record NAV
        account = gateway.query_account()
        nav_records.append({"date": dt, "equity": account["equity"]})
    
    # Lifecycle: Stop strategy
    strategy.on_stop()
    
    logger.info("run_paper_v3.complete", 
                final_equity=account["equity"],
                total_trades=len(trades))
    
    # Convert NAV to Series
    nav_df = pd.DataFrame(nav_records)
    nav_series = nav_df.set_index("date")["equity"]
    nav_series.name = "equity"
    
    # Calculate basic metrics
    metrics = _calculate_metrics(nav_series, initial_cash)
    
    # Unregister event handler
    try:
        events.unregister("order.filled", on_fill)
    except Exception:
        pass
    
    return {
        "account": gateway.query_account(),
        "nav": nav_series,
        "trades": trades,
        "metrics": metrics,
    }


def _calculate_metrics(nav: pd.Series, initial_cash: float) -> Dict[str, float]:
    """Calculate basic performance metrics from NAV series."""
    if len(nav) < 2:
        return {
            "total_return": 0.0,
            "annual_return": 0.0,
            "volatility": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
        }
    
    returns = nav.pct_change().dropna()
    
    total_return = (nav.iloc[-1] / initial_cash - 1) * 100
    annual_factor = 252 / len(nav) if len(nav) > 0 else 1
    annual_return = ((1 + total_return / 100) ** annual_factor - 1) * 100
    
    volatility = returns.std() * (252 ** 0.5) * 100 if len(returns) > 0 else 0
    
    # Max drawdown
    cummax = nav.cummax()
    drawdown = (nav - cummax) / cummax
    max_drawdown = drawdown.min() * 100
    
    # Sharpe ratio (assuming 0 risk-free rate)
    sharpe = (returns.mean() / returns.std() * (252 ** 0.5)) if returns.std() > 0 else 0
    
    return {
        "total_return": round(total_return, 2),
        "annual_return": round(annual_return, 2),
        "volatility": round(volatility, 2),
        "max_drawdown": round(max_drawdown, 2),
        "sharpe_ratio": round(sharpe, 2),
    }


# =============================================================================
# Legacy Runner: StrategyTemplate (Backward Compatibility)
# =============================================================================

def run_paper_legacy(
    template,  # StrategyTemplate
    data_map: Dict[str, pd.DataFrame],
    events: EventEngine,
    *,
    slippage: float = 0.0,
    initial_cash: float = 200_000.0,
) -> Dict[str, Any]:
    """
    Run paper trading with legacy StrategyTemplate (backward compatible).
    
    支持旧的 StrategyTemplate 接口，内部使用 PaperGatewayV3。
    
    Args:
        template: Legacy StrategyTemplate instance
        data_map: Dict mapping symbol -> DataFrame with OHLCV data
        events: EventEngine for publishing trade events
        slippage: Slippage factor (e.g., 0.001 = 0.1%)
        initial_cash: Starting capital
    
    Returns:
        Dict with account state (cash, equity, positions)
    """
    logger.info("run_paper_legacy.start", 
                template_type=type(template).__name__,
                symbols=list(data_map.keys()))
    
    # Validate inputs
    if not data_map:
        raise ValueError("data_map cannot be empty")
    
    # Create V3 gateway
    gw = PaperGatewayV3(events=events, slippage=slippage, initial_cash=initial_cash)
    
    # Inject gateway into template for direct access
    if hasattr(template, '__dict__'):
        template.__dict__['gateway'] = gw
    
    # Strategy lifecycle: Initialize
    template.on_init()
    template.on_start()
    
    # Build timeline from all data
    all_dates = sorted(set().union(*[set(df.index) for df in data_map.values()]))
    
    # Simulation loop
    for dt in all_dates:
        # Phase 1: Match pending orders at open price
        for symbol, df in data_map.items():
            if dt in df.index:
                open_price = float(df.loc[dt, "open"])
                gw.match_orders(symbol, open_price, dt)
        
        # Phase 2: Process bars through strategy
        for symbol, df in data_map.items():
            if dt in df.index:
                row = df.loc[dt]
                bar = pd.Series({
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row.get("volume", 0)),
                })
                
                # Call strategy bar handler
                template.on_bar(symbol, bar)
                
                # Update last price for equity calculation
                gw.update_price(symbol, float(row["close"]))
    
    # Lifecycle: Stop strategy
    template.on_stop()
    
    logger.info("run_paper_legacy.complete")
    
    # Return final account state
    return gw.query_account()


def run_paper_with_nav(
    strategy: Union[BaseStrategy, Any],
    data_map: Dict[str, pd.DataFrame],
    events: EventEngine,
    *,
    slippage: float = 0.0,
    initial_cash: float = 200_000.0,
) -> Dict[str, Any]:
    """
    Run paper trading and return NAV series + account state.
    
    Unified interface that automatically routes to V3 or legacy runner.
    
    Args:
        strategy: BaseStrategy or legacy StrategyTemplate
        data_map: Dict mapping symbol -> DataFrame with OHLCV data
        events: EventEngine for publishing trade events
        slippage: Slippage factor
        initial_cash: Starting capital
    
    Returns:
        Dict with keys:
        - account: Final account state
        - nav: pd.Series of daily equity (indexed by date)
        - trades: List of all filled orders
        - metrics: Performance metrics (V3 only)
    """
    # Route to appropriate runner
    if isinstance(strategy, BaseStrategy):
        return run_paper_v3(strategy, data_map, events,
                          slippage=slippage, initial_cash=initial_cash)
    
    # Legacy path - need to track NAV manually
    logger.info("run_paper_with_nav.legacy", template_type=type(strategy).__name__)
    
    nav_records: List[Dict[str, Any]] = []
    trades: List[Dict[str, Any]] = []
    
    def on_fill(event):
        trade_data = event.data if hasattr(event, 'data') else event
        trades.append(trade_data)
    events.register("order.filled", on_fill)
    
    # Create V3 gateway
    gw = PaperGatewayV3(events=events, slippage=slippage, initial_cash=initial_cash)
    
    if hasattr(strategy, '__dict__'):
        strategy.__dict__['gateway'] = gw
    
    strategy.on_init()
    strategy.on_start()
    
    all_dates = sorted(set().union(*[set(df.index) for df in data_map.values()]))
    
    for dt in all_dates:
        for symbol, df in data_map.items():
            if dt in df.index:
                gw.match_orders(symbol, float(df.loc[dt, "open"]), dt)
        
        for symbol, df in data_map.items():
            if dt in df.index:
                row = df.loc[dt]
                bar = pd.Series({
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row.get("volume", 0)),
                })
                strategy.on_bar(symbol, bar)
                gw.update_price(symbol, float(row["close"]))
        
        account = gw.query_account()
        nav_records.append({"date": dt, "equity": account["equity"]})
    
    strategy.on_stop()
    
    try:
        events.unregister("order.filled", on_fill)
    except Exception:
        pass
    
    nav_df = pd.DataFrame(nav_records)
    nav_series = nav_df.set_index("date")["equity"]
    nav_series.name = "equity"
    
    return {
        "account": gw.query_account(),
        "nav": nav_series,
        "trades": trades,
    }


# =============================================================================
# Example Strategies
# =============================================================================

class SimpleBuyHoldStrategy(BaseStrategy):
    """
    Example V3 strategy: Buy and hold.
    
    Demonstrates the BaseStrategy interface with context usage.
    """
    
    def __init__(self, quantity: int = 100):
        super().__init__()
        self.quantity = quantity
        self._bought = False
    
    def on_init(self) -> None:
        """Initialize strategy state."""
        self._bought = False
        logger.info("SimpleBuyHoldStrategy.on_init", quantity=self.quantity)
    
    def on_bar(self, symbol: str, bar: BarData) -> None:
        """Buy once on first bar."""
        if not self._bought:
            self.ctx.buy(symbol, self.quantity)
            self._bought = True
            logger.info("SimpleBuyHoldStrategy.buy", symbol=symbol, price=bar.close)
    
    def on_stop(self) -> None:
        """Log final state."""
        account = self.ctx.account
        logger.info("SimpleBuyHoldStrategy.on_stop", equity=account.get("equity", 0))


class SimpleMovingAverageStrategy(BaseStrategy):
    """
    Example V3 strategy: Simple moving average crossover.
    
    Uses context.history() for lookback data access.
    """
    
    def __init__(self, period: int = 20, quantity: int = 100):
        super().__init__()
        self.period = period
        self.quantity = quantity
        self._has_position: Dict[str, bool] = {}
    
    def on_init(self) -> None:
        """Initialize position tracking."""
        self._has_position = {}
    
    def on_bar(self, symbol: str, bar: BarData) -> None:
        """Trade based on price vs SMA."""
        # Get historical closes
        history = self.ctx.history(symbol, self.period, "close")
        
        if len(history) < self.period:
            return
        
        sma = history.mean()
        has_pos = self._has_position.get(symbol, False)
        
        # Buy signal: price crosses above SMA
        if bar.close > sma and not has_pos:
            self.ctx.buy(symbol, self.quantity)
            self._has_position[symbol] = True
            logger.debug("SMA.buy", symbol=symbol, price=bar.close, sma=sma)
        
        # Sell signal: price crosses below SMA
        elif bar.close < sma and has_pos:
            self.ctx.sell(symbol, self.quantity)
            self._has_position[symbol] = False
            logger.debug("SMA.sell", symbol=symbol, price=bar.close, sma=sma)


# =============================================================================
# Convenience re-exports for backward compatibility
# =============================================================================

# Keep old function name working, routes to appropriate implementation
def run_paper(
    strategy,
    data_map: Dict[str, pd.DataFrame],
    events: EventEngine,
    *,
    slippage: float = 0.0,
    initial_cash: float = 200_000.0,
) -> Dict[str, Any]:
    """
    Unified paper trading entry point (backward compatible).
    
    Automatically routes to V3 (BaseStrategy) or legacy (StrategyTemplate) runner.
    """
    if isinstance(strategy, BaseStrategy):
        result = run_paper_v3(strategy, data_map, events,
                             slippage=slippage, initial_cash=initial_cash)
        return result["account"]
    else:
        return run_paper_legacy(strategy, data_map, events,
                               slippage=slippage, initial_cash=initial_cash)


__all__ = [
    # V3 API
    "run_paper_v3",
    "run_paper_with_nav",
    # Legacy API
    "run_paper_legacy",
    "run_paper",
    # Example strategies
    "SimpleBuyHoldStrategy",
    "SimpleMovingAverageStrategy",
]
