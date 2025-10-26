"""
Paper Trading Runner

Lightweight runner for executing StrategyTemplate with PaperGateway.
Provides a clean alternative to Backtrader for template-based strategies.
"""
from __future__ import annotations

from typing import Dict, Any
import pandas as pd

from src.strategy.template import StrategyTemplate
from src.core.events import EventEngine
from src.core.paper_gateway import PaperGateway


def run_paper(
    template: StrategyTemplate,
    data_map: Dict[str, pd.DataFrame],
    events: EventEngine,
    *,
    slippage: float = 0.0,
    initial_cash: float = 200_000.0,
) -> Dict[str, Any]:
    """
    Run strategy template with paper trading gateway.
    
    Workflow:
    1. Initialize strategy (template.on_init())
    2. Start strategy (template.on_start())
    3. For each aligned bar across all symbols:
       a. Match pending orders at open price (gateway.match_on_open())
       b. Call strategy for each symbol (template.on_bar())
       c. Update last prices with close (gateway.mark_price())
    4. Stop strategy (template.on_stop())
    5. Return final account state
    
    Architecture:
    - Decoupled from Backtrader (pure Python execution)
    - Event-driven (all orders/trades published to EventEngine)
    - Flexible (strategy can emit custom events)
    - Testable (pure functions, no global state)
    
    Args:
        template: Strategy implementing StrategyTemplate protocol
        data_map: Dict mapping symbol -> DataFrame with OHLCV data
        events: EventEngine for order/trade/custom events
        slippage: Slippage rate (default: 0.0)
        initial_cash: Starting cash balance (default: 200,000)
    
    Returns:
        Final account state from gateway.query_account()
        Keys: balance, equity, positions_value
    
    Example:
        >>> from src.core.events import EventEngine
        >>> from src.core.paper_runner import run_paper
        >>> from src.strategies.ema_template import EMATemplate
        >>> from src.backtest.engine import BacktestEngine
        >>> 
        >>> # Load data
        >>> engine = BacktestEngine()
        >>> data_map = engine._load_data(["600519.SH"], "2024-01-01", "2024-12-31")
        >>> 
        >>> # Create strategy and events
        >>> strategy = EMATemplate()
        >>> strategy.params = {"period": 20}
        >>> events = EventEngine()
        >>> events.start()
        >>> 
        >>> # Run paper trading
        >>> result = run_paper(strategy, data_map, events, slippage=0.001)
        >>> print(f"Final Equity: {result['equity']:.2f}")
        >>> 
        >>> events.stop()
    
    Integration with Event Handlers:
        >>> # Subscribe to order events for logging
        >>> def log_orders(event):
        ...     print(f"Order: {event.data}")
        >>> 
        >>> events.register(EventType.ORDER_SENT, log_orders)
        >>> events.register(EventType.ORDER_FILLED, log_orders)
        >>> 
        >>> result = run_paper(strategy, data_map, events)
    
    Comparison with Backtrader:
    
    Backtrader Approach (current):
    ```python
    cerebro = bt.Cerebro()
    cerebro.addstrategy(MyBacktraderStrategy, period=20)
    cerebro.adddata(bt.feeds.PandasData(...))
    cerebro.run()
    ```
    
    PaperRunner Approach (V2.7.0):
    ```python
    strategy = MyTemplateStrategy()
    strategy.params = {"period": 20}
    result = run_paper(strategy, data_map, events)
    ```
    
    Advantages:
    - Simpler API (no cerebro setup)
    - Framework independent (template not tied to Backtrader)
    - Event-driven (easy to add monitoring/logging)
    - Testable (pure functions)
    - Flexible (can inject custom gateway implementations)
    """
    
    # Create paper trading gateway
    gw = PaperGateway(events, slippage=slippage, initial_cash=initial_cash)
    
    # Store gateway reference in template (optional, for order submission)
    # Strategy can access via: self.gateway.send_order(...)
    if hasattr(template, '__dict__'):
        template.__dict__['gateway'] = gw
    
    # Lifecycle: Initialize strategy
    template.on_init()
    template.on_start()
    
    # Align all symbols' date index for synchronized bar processing
    all_dates = sorted(set().union(*[set(df.index) for df in data_map.values()]))
    
    # Main simulation loop
    for dt in all_dates:
        # Step 1: Match pending orders at current bar's open price
        # (Orders submitted on bar N-1 are filled at bar N's open)
        for symbol, df in data_map.items():
            if dt in df.index:
                open_price = float(df.loc[dt, "open"])
                gw.match_on_open(symbol, open_price)
        
        # Step 2: Let strategy process the bar and potentially submit new orders
        for symbol, df in data_map.items():
            if dt in df.index:
                row = df.loc[dt]
                
                # Convert DataFrame row to Series with OHLCV keys
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
                gw.mark_price(symbol, float(row["close"]))
    
    # Lifecycle: Stop strategy
    template.on_stop()
    
    # Return final account state
    return gw.query_account()


def run_paper_with_nav(
    template: StrategyTemplate,
    data_map: Dict[str, pd.DataFrame],
    events: EventEngine,
    *,
    slippage: float = 0.0,
    initial_cash: float = 200_000.0,
) -> Dict[str, Any]:
    """
    Run paper trading and return NAV series + account state.
    
    Extended version of run_paper() that tracks equity over time.
    
    Args:
        (same as run_paper)
    
    Returns:
        Dict with keys:
        - account: Final account state
        - nav: pd.Series of daily equity (indexed by date)
        - trades: List of all filled orders
    
    Example:
        >>> result = run_paper_with_nav(strategy, data_map, events)
        >>> nav = result["nav"]
        >>> plt.plot(nav)
        >>> plt.title("Strategy NAV")
    """
    # Track NAV and trades
    nav_records = []
    trades = []
    
    # Subscribe to order filled events
    def on_fill(event):
        trades.append(event.data)
    events.register("order.filled", on_fill)
    
    # Create gateway
    gw = PaperGateway(events, slippage=slippage, initial_cash=initial_cash)
    if hasattr(template, '__dict__'):
        template.__dict__['gateway'] = gw
    
    # Strategy lifecycle
    template.on_init()
    template.on_start()
    
    # Simulation loop with NAV tracking
    all_dates = sorted(set().union(*[set(df.index) for df in data_map.values()]))
    
    for dt in all_dates:
        # Match orders
        for symbol, df in data_map.items():
            if dt in df.index:
                gw.match_on_open(symbol, float(df.loc[dt, "open"]))
        
        # Process bars
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
                template.on_bar(symbol, bar)
                gw.mark_price(symbol, float(row["close"]))
        
        # Record NAV
        account = gw.query_account()
        nav_records.append({"date": dt, "equity": account["equity"]})
    
    template.on_stop()
    
    # Convert NAV to Series
    nav_df = pd.DataFrame(nav_records)
    nav_series = nav_df.set_index("date")["equity"]
    nav_series.name = "equity"
    
    return {
        "account": gw.query_account(),
        "nav": nav_series,
        "trades": trades,
    }


# Example: Strategy that uses gateway directly
class SimpleBuyHoldTemplate:
    """
    Example template demonstrating direct gateway usage.
    
    Buys on first bar, holds to end.
    """
    params = {"symbols": ["600519.SH"]}
    
    def on_init(self):
        self.bought = False
    
    def on_start(self):
        pass
    
    def on_bar(self, symbol: str, bar: pd.Series):
        # Buy once on first bar
        if not self.bought and hasattr(self, 'gateway'):
            self.gateway.send_order(symbol, "buy", 100, order_type="market")
            self.bought = True
    
    def on_stop(self):
        pass
