"""
Strategy Template Protocol and Backtrader Adapter

Provides a simplified, framework-independent strategy development interface.
Strategies implementing StrategyTemplate can be adapted to Backtrader or custom runners.

Enhanced with Context interface for unified data/order access across engines.
"""
from __future__ import annotations

from typing import Protocol, Dict, Any, Type, Optional, Callable, List
from dataclasses import dataclass, field
from datetime import datetime
import pandas as pd

try:
    import backtrader as bt
except ImportError as exc:
    raise ImportError("backtrader is required: pip install backtrader") from exc


# ---------------------------------------------------------------------------
# Context Interface - Unified API for Strategy Execution
# ---------------------------------------------------------------------------

@dataclass
class Position:
    """Position information for a symbol."""
    symbol: str
    size: float = 0.0  # Positive for long, negative for short
    avg_price: float = 0.0
    market_value: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0


@dataclass
class Account:
    """Account information."""
    cash: float = 100000.0
    total_value: float = 100000.0
    available: float = 100000.0
    margin: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0


class Context(Protocol):
    """
    Unified context interface for strategy execution.
    
    Provides framework-independent access to:
    - Market data (current prices, history)
    - Order management (buy, sell, cancel)
    - Position/Account information
    - Strategy state
    
    This allows strategies to work across different execution engines
    (Backtrader, PaperRunner, LiveTrader) without modification.
    """
    
    # Account & Position Information
    account: Account
    positions: Dict[str, Position]
    
    # Market Data Access
    def current_price(self, symbol: str, field: str = "close") -> Optional[float]:
        """
        Get current price for a symbol.
        
        Args:
            symbol: Symbol identifier
            field: Price field ("open", "high", "low", "close")
        
        Returns:
            Current price or None if not available
        """
        ...
    
    def history(
        self, 
        symbol: str, 
        fields: List[str], 
        periods: int,
        frequency: str = "1d"
    ) -> pd.DataFrame:
        """
        Get historical data for a symbol.
        
        Args:
            symbol: Symbol identifier
            fields: List of fields to retrieve
            periods: Number of periods to look back
            frequency: Data frequency ("1d", "1h", "5m", etc.)
        
        Returns:
            DataFrame with requested fields and periods
        """
        ...
    
    # Order Management
    def buy(
        self, 
        symbol: str, 
        size: Optional[float] = None,
        price: Optional[float] = None,
        order_type: str = "market"
    ) -> str:
        """
        Send buy order.
        
        Args:
            symbol: Symbol to buy
            size: Order size (None for auto-sizing)
            price: Limit price (None for market order)
            order_type: "market" or "limit"
        
        Returns:
            Order ID
        """
        ...
    
    def sell(
        self, 
        symbol: str, 
        size: Optional[float] = None,
        price: Optional[float] = None,
        order_type: str = "market"
    ) -> str:
        """
        Send sell order.
        
        Args:
            symbol: Symbol to sell
            size: Order size (None for full position)
            price: Limit price (None for market order)
            order_type: "market" or "limit"
        
        Returns:
            Order ID
        """
        ...
    
    def cancel(self, order_id: str) -> bool:
        """
        Cancel an order.
        
        Args:
            order_id: Order ID to cancel
        
        Returns:
            True if successful
        """
        ...
    
    # Utility Methods
    def log(self, message: str, level: str = "info") -> None:
        """Log a message."""
        ...
    
    def get_datetime(self) -> datetime:
        """Get current bar datetime."""
        ...


class StrategyTemplate(Protocol):
    """
    Simplified strategy protocol decoupled from execution engine.
    
    Lifecycle methods:
    - on_init(ctx): Initialize indicators and state (called once before data)
    - on_start(ctx): Strategy starts (called once after data loaded)
    - on_bar(ctx, symbol, bar): Process each bar (called for every symbol/bar)
    - on_stop(ctx): Strategy stops (called once after all bars processed)
    
    State management:
    - self.params: Dict[str, Any] - Strategy parameters
    - ctx: Context - Unified execution context (data, orders, positions)
    
    Example:
        >>> class MyStrategy(StrategyTemplate):
        ...     params = {"period": 20}
        ...     
        ...     def on_init(self, ctx: Context):
        ...         self.state = {}
        ...     
        ...     def on_bar(self, ctx: Context, symbol: str, bar: pd.Series):
        ...         # Access current price
        ...         price = ctx.current_price(symbol)
        ...         
        ...         # Access history
        ...         hist = ctx.history(symbol, ["close"], 20)
        ...         
        ...         # Place order
        ...         if signal_condition:
        ...             ctx.buy(symbol, size=100)
    """
    
    params: Dict[str, Any]
    
    def on_init(self, ctx: Context) -> None:
        """
        Initialize indicators and state.
        
        Called once before any data is processed.
        
        Args:
            ctx: Execution context
        """
        ...
    
    def on_start(self, ctx: Context) -> None:
        """
        Strategy starts.
        
        Called once after data is loaded but before first bar.
        
        Args:
            ctx: Execution context
        """
        ...
    
    def on_bar(self, ctx: Context, symbol: str, bar: pd.Series) -> None:
        """
        Process each bar.
        
        Called for every symbol on every bar.
        
        Args:
            ctx: Execution context
            symbol: Symbol identifier (e.g., "600519.SH")
            bar: OHLCV data as pd.Series with keys:
                 ["open", "high", "low", "close", "volume"]
        """
        ...
    
    def on_stop(self, ctx: Context) -> None:
        """
        Strategy stops.
        
        Called once after all bars are processed.
        
        Args:
            ctx: Execution context
        """
        ...


# ---------------------------------------------------------------------------
# Backtrader Context Implementation
# ---------------------------------------------------------------------------

class BacktraderContext:
    """
    Context implementation for Backtrader strategies.
    
    Provides the Context interface using Backtrader's internal APIs.
    """
    
    def __init__(self, bt_strategy: bt.Strategy):
        """
        Initialize context with Backtrader strategy reference.
        
        Args:
            bt_strategy: Backtrader strategy instance
        """
        self._bt = bt_strategy
        self._symbol_map: Dict[str, Any] = {}
        
        # Build symbol map
        for i, data in enumerate(bt_strategy.datas):
            name = getattr(data, '_name', None) or f"symbol_{i}"
            self._symbol_map[name] = data
    
    @property
    def account(self) -> Account:
        """Get account information."""
        broker = self._bt.broker
        return Account(
            cash=broker.getcash(),
            total_value=broker.getvalue(),
            available=broker.getcash(),
            margin=0.0,
            pnl=broker.getvalue() - broker.startingcash,
            pnl_pct=(broker.getvalue() - broker.startingcash) / broker.startingcash * 100
        )
    
    @property
    def positions(self) -> Dict[str, Position]:
        """Get all positions."""
        result = {}
        for symbol, data in self._symbol_map.items():
            pos = self._bt.getposition(data)
            if pos.size != 0:
                result[symbol] = Position(
                    symbol=symbol,
                    size=pos.size,
                    avg_price=pos.price,
                    market_value=pos.size * data.close[0],
                    pnl=pos.size * (data.close[0] - pos.price),
                    pnl_pct=(data.close[0] - pos.price) / pos.price * 100 if pos.price != 0 else 0.0
                )
        return result
    
    def current_price(self, symbol: str, field: str = "close") -> Optional[float]:
        """Get current price for symbol."""
        data = self._symbol_map.get(symbol)
        if data is None:
            return None
        
        field_map = {
            "open": data.open,
            "high": data.high,
            "low": data.low,
            "close": data.close,
            "volume": getattr(data, "volume", None)
        }
        
        line = field_map.get(field.lower())
        if line is None:
            return None
        
        try:
            return float(line[0])
        except (IndexError, TypeError):
            return None
    
    def history(
        self, 
        symbol: str, 
        fields: List[str], 
        periods: int,
        frequency: str = "1d"
    ) -> pd.DataFrame:
        """Get historical data."""
        data = self._symbol_map.get(symbol)
        if data is None:
            return pd.DataFrame()
        
        result = {}
        field_map = {
            "open": data.open,
            "high": data.high,
            "low": data.low,
            "close": data.close,
            "volume": getattr(data, "volume", None)
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
        """Cancel order (not fully supported in this implementation)."""
        # Backtrader doesn't provide easy order lookup by ID
        return False
    
    def log(self, message: str, level: str = "info") -> None:
        """Log message."""
        try:
            dt = self._bt.datetime.datetime()
            print(f"[{dt}] {level.upper()}: {message}")
        except (IndexError, AttributeError):
            # During initialization, datetime may not be available
            print(f"[INIT] {level.upper()}: {message}")
    
    def get_datetime(self) -> datetime:
        """Get current bar datetime."""
        try:
            return self._bt.datetime.datetime()
        except (IndexError, AttributeError):
            # Return a default datetime during initialization
            return datetime.now()


# ---------------------------------------------------------------------------
# Backtrader Adapter
# ---------------------------------------------------------------------------

class BacktraderAdapter:
    """
    Adapts StrategyTemplate to Backtrader.Strategy.
    
    Bridges the simplified template interface to Backtrader's execution model.
    Now provides Context interface for unified data/order access.
    
    Usage:
        >>> adapter = BacktraderAdapter(MyTemplateStrategy, period=20, threshold=0.02)
        >>> bt_strategy = adapter.to_bt_strategy()
        >>> cerebro.addstrategy(bt_strategy)
    
    Features:
    - Automatic lifecycle mapping (on_init -> __init__, on_bar -> next, etc.)
    - Context interface for data/order access
    - Parameter passing from kwargs to template.params
    - Multi-symbol support via data name tracking
    """
    
    def __init__(self, template_cls: Type[StrategyTemplate], **params: Any):
        """
        Initialize adapter with template class and parameters.
        
        Args:
            template_cls: Strategy class implementing StrategyTemplate protocol
            **params: Strategy parameters (passed to template.params)
        """
        self.template_cls = template_cls
        self.params = params
    
    def to_bt_strategy(self) -> Type[bt.Strategy]:
        """
        Generate Backtrader Strategy class from template.
        
        Returns:
            Backtrader Strategy class ready for cerebro.addstrategy()
        
        Implementation:
        - Creates dynamic Backtrader Strategy class
        - Instantiates template in __init__
        - Maps lifecycle: __init__ -> on_init, start -> on_start, 
          next -> on_bar, stop -> on_stop
        - Converts Backtrader data lines to pandas Series per bar
        """
        
        # Capture template class and params in closure
        tmpl_cls = self.template_cls
        params_dict = dict(self.params)
        
        class _BacktraderTemplateStrategy(bt.Strategy):
            """
            Dynamically generated Backtrader strategy wrapping StrategyTemplate.
            
            Internal implementation detail - users should not instantiate directly.
            """
            
            # Convert params dict to Backtrader params tuple
            params = tuple((k, v) for k, v in params_dict.items())
            
            def __init__(self):
                """
                Initialize template and map data feeds.
                
                Lifecycle: Backtrader __init__ -> Template on_init()
                """
                # Instantiate template
                self._tmpl: StrategyTemplate = tmpl_cls()
                
                # Pass parameters to template
                self._tmpl.params = dict(self.params.__dict__)
                
                # Create context
                self._ctx = BacktraderContext(self)
                
                # Call template init
                self._tmpl.on_init(self._ctx)
            
            def start(self):
                """
                Strategy starts.
                
                Lifecycle: Backtrader start() -> Template on_start()
                """
                self._tmpl.on_start(self._ctx)
            
            def next(self):
                """
                Process each bar.
                
                Lifecycle: Backtrader next() -> Template on_bar(ctx, symbol, bar)
                
                Called once per bar for the synchronized data feeds.
                Converts Backtrader's line notation to pandas Series.
                """
                for name, data in self._ctx._symbol_map.items():
                    # Convert Backtrader data lines to pandas Series
                    bar = pd.Series({
                        "open": float(data.open[0]),
                        "high": float(data.high[0]),
                        "low": float(data.low[0]),
                        "close": float(data.close[0]),
                        "volume": float(getattr(data, "volume", [0])[0]),
                    })
                    
                    # Call template's bar handler
                    self._tmpl.on_bar(self._ctx, name, bar)
            
            def stop(self):
                """
                Strategy stops.
                
                Lifecycle: Backtrader stop() -> Template on_stop()
                """
                self._tmpl.on_stop(self._ctx)
        
        return _BacktraderTemplateStrategy


# Convenience function for direct registration
def build_bt_strategy(template_cls: Type[StrategyTemplate], **params: Any) -> Type[bt.Strategy]:
    """
    Convenience function to build Backtrader strategy from template.
    
    Args:
        template_cls: Strategy class implementing StrategyTemplate
        **params: Strategy parameters
    
    Returns:
        Backtrader Strategy class
    
    Example:
        >>> EMAStrategy = build_bt_strategy(EMATemplate, period=20)
        >>> cerebro.addstrategy(EMAStrategy)
    """
    return BacktraderAdapter(template_cls, **params).to_bt_strategy()
