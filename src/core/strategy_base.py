"""
Unified Strategy Base Class

Provides a framework-independent strategy interface that can be executed
on both Backtrader (for backtesting) and EventEngine (for paper/live trading).

V3.0.0: Initial release - "Write Once, Run Anywhere" strategy architecture.

Key Features:
- Single strategy definition works across all execution engines
- Context interface abstracts away engine-specific details
- Built-in support for common trading operations
- Easy migration from Backtrader-only strategies

Usage:
    >>> from src.core.strategy_base import BaseStrategy, BarData
    >>> 
    >>> class MyMAStrategy(BaseStrategy):
    ...     params = {"fast_period": 10, "slow_period": 30}
    ...     
    ...     def on_init(self, ctx):
    ...         self.fast_ma = []
    ...         self.slow_ma = []
    ...     
    ...     def on_bar(self, ctx, bar):
    ...         # Your strategy logic here
    ...         price = bar.close
    ...         # ... calculate indicators, generate signals
    ...         if buy_signal:
    ...             self.buy(ctx, bar.symbol, size=100)
    >>> 
    >>> # For Backtrader:
    >>> from src.core.strategy_base import BacktraderStrategyAdapter
    >>> bt_strategy = BacktraderStrategyAdapter.wrap(MyMAStrategy, fast_period=10)
    >>> cerebro.addstrategy(bt_strategy)
    >>> 
    >>> # For EventEngine/PaperTrading:
    >>> from src.core.paper_runner_v3 import run_paper_v3
    >>> result = run_paper_v3(MyMAStrategy(fast_period=10), data_map, events)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Type
from dataclasses import dataclass, field
from datetime import datetime
import logging

# Import unified interfaces
from src.core.interfaces import (
    BarData, PositionInfo, AccountInfo, StrategyContext,
    Side, OrderTypeEnum
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Base Strategy Class
# ---------------------------------------------------------------------------

class BaseStrategy(ABC):
    """
    Unified Strategy Base Class.
    
    Provides a framework-independent interface for strategy development.
    Strategies inheriting from this class can run on:
    - Backtrader (via BacktraderStrategyAdapter)
    - EventEngine / PaperRunner (direct execution)
    - LiveRunner (future)
    
    Lifecycle:
        1. __init__(): Store parameters
        2. on_init(ctx): Initialize indicators, state variables
        3. on_start(ctx): Called once before first bar
        4. on_bar(ctx, bar): Called for each bar - main logic
        5. on_stop(ctx): Called after last bar - cleanup
    
    Attributes:
        params: Strategy parameters (set via __init__ or class attribute)
        variables: Runtime variables for state tracking
        
    Example:
        >>> class DualMAStrategy(BaseStrategy):
        ...     params = {"fast": 10, "slow": 30}
        ...     
        ...     def on_init(self, ctx):
        ...         self.fast_ma = []
        ...         self.slow_ma = []
        ...     
        ...     def on_bar(self, ctx, bar):
        ...         # Calculate moving averages
        ...         hist = ctx.history(bar.symbol, ["close"], self.params["slow"])
        ...         fast_ma = hist["close"].tail(self.params["fast"]).mean()
        ...         slow_ma = hist["close"].mean()
        ...         
        ...         # Generate signals
        ...         pos = ctx.positions.get(bar.symbol)
        ...         if fast_ma > slow_ma and (pos is None or pos.is_flat):
        ...             self.buy(ctx, bar.symbol, size=100)
        ...         elif fast_ma < slow_ma and pos and pos.is_long:
        ...             self.sell(ctx, bar.symbol)
    """
    
    # Default parameters (override in subclass)
    params: Dict[str, Any] = {}
    
    def __init__(self, **kwargs):
        """
        Initialize strategy with parameters.
        
        Args:
            **kwargs: Strategy parameters (override class defaults)
        """
        # Merge class params with instance params
        self.params = {**self.__class__.params, **kwargs}
        
        # Runtime state variables
        self.variables: Dict[str, Any] = {}
        
        # Internal references (set by runner)
        self._ctx: Optional[StrategyContext] = None
        self._symbols: List[str] = []
    
    def set_context(self, ctx: StrategyContext) -> None:
        """Set the execution context (called by runner)."""
        self._ctx = ctx
    
    def set_symbols(self, symbols: List[str]) -> None:
        """Set the symbols this strategy trades (called by runner)."""
        self._symbols = symbols
    
    # ---------------------------------------------------------------------------
    # Lifecycle Methods (Override in subclass)
    # ---------------------------------------------------------------------------
    
    @abstractmethod
    def on_init(self, ctx: StrategyContext) -> None:
        """
        Initialize strategy state and indicators.
        
        Called once before any data is processed. Use this to:
        - Initialize indicator buffers
        - Set up state variables
        - Pre-calculate static values
        
        Args:
            ctx: Execution context
        """
        pass
    
    def on_start(self, ctx: StrategyContext) -> None:
        """
        Strategy starts.
        
        Called once after data is loaded but before first bar.
        Override for any start-up logic.
        
        Args:
            ctx: Execution context
        """
        pass
    
    @abstractmethod
    def on_bar(self, ctx: StrategyContext, bar: BarData) -> None:
        """
        Process each bar - main strategy logic.
        
        Called for every bar for every symbol. This is where you:
        - Update indicators
        - Generate trading signals
        - Execute orders
        
        Args:
            ctx: Execution context
            bar: Current bar data
        """
        pass
    
    def on_stop(self, ctx: StrategyContext) -> None:
        """
        Strategy stops.
        
        Called once after all bars are processed.
        Override for cleanup or final reporting.
        
        Args:
            ctx: Execution context
        """
        pass
    
    # ---------------------------------------------------------------------------
    # Trading Methods (Convenience wrappers)
    # ---------------------------------------------------------------------------
    
    def buy(
        self,
        ctx: StrategyContext,
        symbol: str,
        size: Optional[float] = None,
        price: Optional[float] = None,
        order_type: str = "market"
    ) -> str:
        """
        Send a buy order.
        
        Convenience wrapper around ctx.buy() with logging.
        
        Args:
            ctx: Execution context
            symbol: Symbol to buy
            size: Order size (None for auto-sizing)
            price: Limit price (None for market order)
            order_type: "market" or "limit"
            
        Returns:
            Order ID
        """
        order_id = ctx.buy(symbol, size, price, order_type)
        if order_id:
            logger.debug(f"BUY {symbol} size={size} price={price} type={order_type} -> {order_id}")
        return order_id
    
    def sell(
        self,
        ctx: StrategyContext,
        symbol: str,
        size: Optional[float] = None,
        price: Optional[float] = None,
        order_type: str = "market"
    ) -> str:
        """
        Send a sell order.
        
        Convenience wrapper around ctx.sell() with logging.
        
        Args:
            ctx: Execution context
            symbol: Symbol to sell
            size: Order size (None for full position)
            price: Limit price (None for market order)
            order_type: "market" or "limit"
            
        Returns:
            Order ID
        """
        order_id = ctx.sell(symbol, size, price, order_type)
        if order_id:
            logger.debug(f"SELL {symbol} size={size} price={price} type={order_type} -> {order_id}")
        return order_id
    
    def close_position(
        self,
        ctx: StrategyContext,
        symbol: str,
        price: Optional[float] = None,
        order_type: str = "market"
    ) -> str:
        """
        Close entire position for a symbol.
        
        Args:
            ctx: Execution context
            symbol: Symbol to close
            price: Limit price (None for market order)
            order_type: "market" or "limit"
            
        Returns:
            Order ID or empty string if no position
        """
        pos = ctx.positions.get(symbol)
        if pos is None or pos.is_flat:
            return ""
        
        if pos.is_long:
            return self.sell(ctx, symbol, size=pos.size, price=price, order_type=order_type)
        else:
            return self.buy(ctx, symbol, size=abs(pos.size), price=price, order_type=order_type)
    
    # ---------------------------------------------------------------------------
    # Utility Methods
    # ---------------------------------------------------------------------------
    
    def get_position(self, ctx: StrategyContext, symbol: str) -> Optional[PositionInfo]:
        """Get position for symbol (None if no position)."""
        return ctx.positions.get(symbol)
    
    def has_position(self, ctx: StrategyContext, symbol: str) -> bool:
        """Check if there's an open position for symbol."""
        pos = ctx.positions.get(symbol)
        return pos is not None and not pos.is_flat
    
    def is_long(self, ctx: StrategyContext, symbol: str) -> bool:
        """Check if position is long."""
        pos = ctx.positions.get(symbol)
        return pos is not None and pos.is_long
    
    def is_short(self, ctx: StrategyContext, symbol: str) -> bool:
        """Check if position is short."""
        pos = ctx.positions.get(symbol)
        return pos is not None and pos.is_short
    
    def log(self, ctx: StrategyContext, message: str, level: str = "info") -> None:
        """Log a message with timestamp."""
        ctx.log(message, level)


# ---------------------------------------------------------------------------
# Backtrader Adapter
# ---------------------------------------------------------------------------

class BacktraderStrategyAdapter:
    """
    Adapter to run BaseStrategy on Backtrader.
    
    Wraps a BaseStrategy subclass and generates a Backtrader-compatible
    strategy class that can be added to cerebro.
    
    Usage:
        >>> bt_strategy = BacktraderStrategyAdapter.wrap(MyStrategy, fast=10, slow=30)
        >>> cerebro.addstrategy(bt_strategy)
    """
    
    @staticmethod
    def wrap(strategy_cls: Type[BaseStrategy], **params) -> Type:
        """
        Wrap a BaseStrategy class for Backtrader.
        
        Args:
            strategy_cls: Strategy class (must inherit from BaseStrategy)
            **params: Strategy parameters
            
        Returns:
            Backtrader-compatible strategy class
        """
        try:
            import backtrader as bt
        except ImportError:
            raise ImportError("backtrader is required: pip install backtrader")
        
        # Import here to avoid circular imports
        from src.core.interfaces import BarData
        
        # Capture in closure
        _strategy_cls = strategy_cls
        _params = params
        
        class _BTWrapper(bt.Strategy):
            """Backtrader wrapper for BaseStrategy."""
            
            # Convert params to Backtrader format
            params = tuple(_params.items())
            
            def __init__(self):
                """Initialize the wrapper."""
                # Create strategy instance
                self._strategy: BaseStrategy = _strategy_cls(**dict(self.params.__dict__))
                
                # Create context adapter
                self._ctx = _BacktraderContextAdapter(self)
                self._strategy.set_context(self._ctx)
                
                # Build symbol list
                symbols = []
                for data in self.datas:
                    name = getattr(data, '_name', None) or f"data_{len(symbols)}"
                    symbols.append(name)
                self._strategy.set_symbols(symbols)
                
                # Call strategy init
                self._strategy.on_init(self._ctx)
            
            def start(self):
                """Backtrader start -> Strategy on_start."""
                self._strategy.on_start(self._ctx)
            
            def next(self):
                """Backtrader next -> Strategy on_bar for each data feed."""
                for i, data in enumerate(self.datas):
                    name = getattr(data, '_name', None) or f"data_{i}"
                    
                    # Convert to BarData
                    bar = BarData(
                        symbol=name,
                        timestamp=self.datetime.datetime(),
                        open=float(data.open[0]),
                        high=float(data.high[0]),
                        low=float(data.low[0]),
                        close=float(data.close[0]),
                        volume=float(getattr(data, 'volume', [0])[0]),
                    )
                    
                    # Call strategy
                    self._strategy.on_bar(self._ctx, bar)
            
            def stop(self):
                """Backtrader stop -> Strategy on_stop."""
                self._strategy.on_stop(self._ctx)
        
        return _BTWrapper


class _BacktraderContextAdapter:
    """
    Adapts Backtrader's API to the StrategyContext interface.
    
    This allows BaseStrategy to interact with Backtrader transparently.
    """
    
    def __init__(self, bt_strategy):
        """
        Initialize with Backtrader strategy reference.
        
        Args:
            bt_strategy: Backtrader strategy instance
        """
        self._bt = bt_strategy
        self._symbol_map: Dict[str, Any] = {}
        
        # Build symbol map
        for i, data in enumerate(bt_strategy.datas):
            name = getattr(data, '_name', None) or f"data_{i}"
            self._symbol_map[name] = data
    
    @property
    def account(self) -> AccountInfo:
        """Get account information."""
        broker = self._bt.broker
        starting = getattr(broker, 'startingcash', broker.getcash())
        return AccountInfo(
            account_id="backtrader",
            cash=broker.getcash(),
            total_value=broker.getvalue(),
            available=broker.getcash(),
            unrealized_pnl=broker.getvalue() - starting,
        )
    
    @property
    def positions(self) -> Dict[str, PositionInfo]:
        """Get all positions."""
        result = {}
        for symbol, data in self._symbol_map.items():
            pos = self._bt.getposition(data)
            if pos.size != 0:
                market_value = pos.size * data.close[0]
                result[symbol] = PositionInfo(
                    symbol=symbol,
                    size=pos.size,
                    avg_price=pos.price,
                    market_value=market_value,
                    unrealized_pnl=pos.size * (data.close[0] - pos.price),
                )
        return result
    
    def current_price(self, symbol: str, field: str = "close") -> Optional[float]:
        """Get current price."""
        data = self._symbol_map.get(symbol)
        if data is None:
            return None
        
        field_map = {
            "open": data.open,
            "high": data.high,
            "low": data.low,
            "close": data.close,
        }
        
        line = field_map.get(field.lower())
        if line is None:
            return None
        
        try:
            return float(line[0])
        except (IndexError, TypeError):
            return None
    
    def get_bar(self, symbol: str) -> Optional[BarData]:
        """Get current bar data."""
        data = self._symbol_map.get(symbol)
        if data is None:
            return None
        
        try:
            return BarData(
                symbol=symbol,
                timestamp=self._bt.datetime.datetime(),
                open=float(data.open[0]),
                high=float(data.high[0]),
                low=float(data.low[0]),
                close=float(data.close[0]),
                volume=float(getattr(data, 'volume', [0])[0]),
            )
        except (IndexError, TypeError):
            return None
    
    def history(
        self, 
        symbol: str, 
        fields: List[str], 
        periods: int,
        frequency: str = "1d"
    ):
        """Get historical data."""
        import pandas as pd
        
        data = self._symbol_map.get(symbol)
        if data is None:
            return pd.DataFrame()
        
        result = {}
        field_map = {
            "open": data.open,
            "high": data.high,
            "low": data.low,
            "close": data.close,
            "volume": getattr(data, "volume", None),
        }
        
        for field in fields:
            line = field_map.get(field.lower())
            if line is not None:
                try:
                    values = [float(line[-i]) for i in range(periods, 0, -1)]
                    result[field] = values
                except (IndexError, TypeError):
                    result[field] = [None] * periods
        
        return pd.DataFrame(result)
    
    def buy(
        self, 
        symbol: str, 
        size: Optional[float] = None,
        price: Optional[float] = None,
        order_type: str = "market"
    ) -> str:
        """Send buy order."""
        import backtrader as bt
        
        data = self._symbol_map.get(symbol)
        if data is None:
            return ""
        
        # Auto-size: 10% of cash
        if size is None:
            size = int(self.account.cash * 0.1 / data.close[0])
        
        if order_type == "limit" and price is not None:
            order = self._bt.buy(data=data, size=size, price=price, exectype=bt.Order.Limit)
        else:
            order = self._bt.buy(data=data, size=size)
        
        return str(order.ref) if order else ""
    
    def sell(
        self, 
        symbol: str, 
        size: Optional[float] = None,
        price: Optional[float] = None,
        order_type: str = "market"
    ) -> str:
        """Send sell order."""
        import backtrader as bt
        
        data = self._symbol_map.get(symbol)
        if data is None:
            return ""
        
        # Auto-size: full position
        if size is None:
            pos = self._bt.getposition(data)
            size = pos.size
        
        if order_type == "limit" and price is not None:
            order = self._bt.sell(data=data, size=size, price=price, exectype=bt.Order.Limit)
        else:
            order = self._bt.sell(data=data, size=size)
        
        return str(order.ref) if order else ""
    
    def cancel(self, order_id: str) -> bool:
        """Cancel order."""
        # Backtrader doesn't provide easy order lookup by ID
        return False
    
    def log(self, message: str, level: str = "info") -> None:
        """Log message."""
        try:
            dt = self._bt.datetime.datetime()
            print(f"[{dt}] {level.upper()}: {message}")
        except (IndexError, AttributeError):
            print(f"[INIT] {level.upper()}: {message}")
    
    def get_datetime(self) -> datetime:
        """Get current bar datetime."""
        try:
            return self._bt.datetime.datetime()
        except (IndexError, AttributeError):
            return datetime.now()


# ---------------------------------------------------------------------------
# Example Strategy
# ---------------------------------------------------------------------------

class ExampleDualMAStrategy(BaseStrategy):
    """
    Example: Dual Moving Average Crossover Strategy.
    
    Demonstrates the BaseStrategy interface with a simple MA crossover.
    
    Parameters:
        fast_period: Fast MA period (default: 10)
        slow_period: Slow MA period (default: 30)
    """
    
    params = {
        "fast_period": 10,
        "slow_period": 30,
    }
    
    def on_init(self, ctx: StrategyContext) -> None:
        """Initialize state."""
        self.variables["prev_fast"] = None
        self.variables["prev_slow"] = None
    
    def on_bar(self, ctx: StrategyContext, bar: BarData) -> None:
        """Process bar and generate signals."""
        symbol = bar.symbol
        
        # Get history
        hist = ctx.history(symbol, ["close"], self.params["slow_period"])
        if len(hist) < self.params["slow_period"]:
            return
        
        # Calculate MAs
        fast_ma = hist["close"].tail(self.params["fast_period"]).mean()
        slow_ma = hist["close"].mean()
        
        # Get previous values
        prev_fast = self.variables.get("prev_fast")
        prev_slow = self.variables.get("prev_slow")
        
        # Update for next bar
        self.variables["prev_fast"] = fast_ma
        self.variables["prev_slow"] = slow_ma
        
        # Skip first bar (no previous values)
        if prev_fast is None:
            return
        
        # Generate signals
        pos = ctx.positions.get(symbol)
        
        # Golden cross: buy signal
        if prev_fast <= prev_slow and fast_ma > slow_ma:
            if pos is None or pos.is_flat:
                self.buy(ctx, symbol, size=100)
                ctx.log(f"Golden Cross: BUY {symbol} @ {bar.close:.2f}")
        
        # Death cross: sell signal
        elif prev_fast >= prev_slow and fast_ma < slow_ma:
            if pos and pos.is_long:
                self.sell(ctx, symbol)
                ctx.log(f"Death Cross: SELL {symbol} @ {bar.close:.2f}")
