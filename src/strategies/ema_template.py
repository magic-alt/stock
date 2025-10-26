"""
EMA Strategy Template Example

Demonstrates simplified strategy development using StrategyTemplate protocol.
This strategy uses exponential moving average crossover logic.
"""
from __future__ import annotations

from typing import Dict, Any
import pandas as pd

from src.strategy.template import StrategyTemplate, build_bt_strategy


class EMATemplate(StrategyTemplate):
    """
    EMA crossover strategy using template pattern.
    
    Logic:
    - Calculate EMA(period) for each symbol
    - Buy signal: price crosses above EMA
    - Sell signal: price crosses below EMA
    
    This template demonstrates:
    - Per-symbol state management (self.ctx)
    - Parameter access (self.params)
    - Simplified bar processing (no Backtrader complexity)
    - Framework independence (can run on Backtrader or PaperRunner)
    """
    
    params: Dict[str, Any] = {"period": 20}
    
    def on_init(self) -> None:
        """
        Initialize per-symbol context.
        
        Creates a context dictionary for each symbol to store:
        - closes: List of historical close prices
        - ema: Current EMA value
        - position: Current position state (0=flat, 1=long)
        """
        self.ctx: Dict[str, Dict[str, Any]] = {}
    
    def on_start(self) -> None:
        """Strategy starts - no special initialization needed."""
        pass
    
    def on_bar(self, symbol: str, bar: pd.Series) -> None:
        """
        Process each bar for symbol.
        
        Args:
            symbol: Symbol identifier
            bar: OHLCV data with keys ["open", "high", "low", "close", "volume"]
        
        Logic:
        1. Accumulate close prices
        2. Calculate EMA when sufficient data
        3. Detect crossovers and update position state
        
        Note: This is a demonstration - actual order submission would be handled by:
        - Backtrader: via self.buy()/self.sell() in BacktraderAdapter
        - PaperRunner: via gateway.send_order() triggered by events
        """
        # Get or create context for this symbol
        ctx = self.ctx.setdefault(symbol, {
            "closes": [],
            "ema": None,
            "position": 0,
            "last_signal": None,
        })
        
        # Accumulate close prices
        close = float(bar["close"])
        ctx["closes"].append(close)
        
        # Need enough data for EMA calculation
        period = int(self.params.get("period", 20))
        if len(ctx["closes"]) < period:
            return
        
        # Calculate EMA using pandas
        closes_series = pd.Series(ctx["closes"])
        ema = closes_series.ewm(span=period, adjust=False).mean().iloc[-1]
        ctx["ema"] = ema
        
        # Detect crossovers
        price = close
        prev_position = ctx["position"]
        
        # Buy signal: price crosses above EMA
        if price > ema and prev_position == 0:
            ctx["position"] = 1
            ctx["last_signal"] = "BUY"
            # In production: emit event or call gateway.send_order()
            # self.events.put(Event(EventType.STRATEGY_SIGNAL, {
            #     "symbol": symbol, "action": "BUY", "price": price
            # }))
        
        # Sell signal: price crosses below EMA
        elif price < ema and prev_position == 1:
            ctx["position"] = 0
            ctx["last_signal"] = "SELL"
            # In production: emit event or call gateway.send_order()
            # self.events.put(Event(EventType.STRATEGY_SIGNAL, {
            #     "symbol": symbol, "action": "SELL", "price": price
            # }))
    
    def on_stop(self) -> None:
        """
        Strategy stops - could log summary here.
        
        Example:
            for symbol, ctx in self.ctx.items():
                print(f"{symbol}: Final position={ctx['position']}, "
                      f"Last signal={ctx.get('last_signal')}")
        """
        pass


# Export Backtrader-compatible strategy factory
def build_ema_strategy(**params: Any):
    """
    Factory function to create Backtrader strategy from EMA template.
    
    Args:
        **params: Strategy parameters (e.g., period=20)
    
    Returns:
        Backtrader Strategy class
    
    Usage:
        >>> # In strategy_modules.py or backtrader_registry.py
        >>> EMA_TEMPLATE_MODULE = StrategyModule(
        ...     name="ema_template",
        ...     description="EMA crossover using template pattern",
        ...     strategy_cls=build_ema_strategy,  # Factory function
        ...     param_names=["period"],
        ...     defaults={"period": 20},
        ...     multi_symbol=False,
        ... )
    """
    return build_bt_strategy(EMATemplate, **params)


# Example usage in standalone script
if __name__ == "__main__":
    """
    Demonstration of template usage with Backtrader.
    
    This shows how the template can be adapted to Backtrader
    and run with the existing BacktestEngine.
    """
    import sys
    sys.path.insert(0, "e:/work/Project/stock")
    
    from src.backtest.engine import BacktestEngine
    
    # Create engine
    engine = BacktestEngine(source="akshare")
    
    # Load data
    data_map = engine._load_data(["600519.SH"], "2024-01-01", "2024-01-31")
    
    print("EMA Template Strategy Demonstration")
    print("=" * 60)
    print(f"Data loaded: {sum(len(df) for df in data_map.values())} bars")
    
    # Note: To actually run this with the engine, we'd need to:
    # 1. Register the strategy in STRATEGY_REGISTRY
    # 2. Use engine.run_strategy("ema_template", ...)
    # 
    # Or use PaperRunner (Patch 4) for direct template execution:
    # from src.core.paper_runner import run_paper
    # template = EMATemplate()
    # template.params = {"period": 20}
    # result = run_paper(template, data_map, events)
    
    print("\nTemplate pattern advantages:")
    print("- Simplified development (no Backtrader complexity)")
    print("- Framework independent (works with PaperRunner)")
    print("- Easier to test (pure Python, no magic)")
    print("- Event-driven ready (can emit strategy.signal events)")
