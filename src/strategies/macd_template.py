"""
MACD Strategy Template Example

Demonstrates advanced strategy template with multiple indicators.
Uses MACD (Moving Average Convergence Divergence) crossover logic.
"""
from __future__ import annotations

from typing import Dict, Any
import pandas as pd
import numpy as np

from src.strategy.template import StrategyTemplate, build_bt_strategy


class MACDTemplate(StrategyTemplate):
    """
    MACD crossover strategy using template pattern.
    
    Logic:
    - Calculate MACD line, Signal line, and Histogram
    - Buy signal: MACD line crosses above Signal line (Golden cross)
    - Sell signal: MACD line crosses below Signal line (Death cross)
    - Optional: Additional filters (histogram direction, zero-line cross)
    
    Parameters:
    - fast: Fast EMA period (default: 12)
    - slow: Slow EMA period (default: 26)
    - signal: Signal EMA period (default: 9)
    - use_histogram_filter: Only trade when histogram confirms (default: True)
    
    This template demonstrates:
    - Multi-indicator calculation (MACD + Signal + Histogram)
    - Advanced state management (previous values for crossover detection)
    - Parameter-based feature toggles (use_histogram_filter)
    - Signal confirmation logic
    """
    
    params: Dict[str, Any] = {
        "fast": 12,
        "slow": 26,
        "signal": 9,
        "use_histogram_filter": True,
    }
    
    def on_init(self) -> None:
        """
        Initialize per-symbol context.
        
        Creates a context dictionary for each symbol to store:
        - closes: Historical close prices
        - macd: Current MACD value
        - signal: Current Signal line value
        - histogram: Current histogram value
        - prev_macd: Previous MACD value (for crossover detection)
        - prev_signal: Previous Signal value
        - position: Current position state (0=flat, 1=long)
        """
        self.ctx: Dict[str, Dict[str, Any]] = {}
    
    def on_start(self) -> None:
        """Strategy starts - could pre-load historical data if available."""
        pass
    
    def _calculate_ema(self, series: pd.Series, period: int) -> float:
        """
        Calculate EMA for a series.
        
        Args:
            series: Price series
            period: EMA period
        
        Returns:
            Latest EMA value
        """
        if len(series) < period:
            return np.nan
        return series.ewm(span=period, adjust=False).mean().iloc[-1]
    
    def _calculate_macd(self, closes: list, fast: int, slow: int, signal: int) -> tuple:
        """
        Calculate MACD, Signal, and Histogram.
        
        Args:
            closes: Historical close prices
            fast: Fast EMA period
            slow: Slow EMA period
            signal: Signal EMA period
        
        Returns:
            Tuple of (macd, signal, histogram) or (None, None, None) if insufficient data
        """
        if len(closes) < slow:
            return None, None, None
        
        # Convert to pandas Series
        close_series = pd.Series(closes)
        
        # Calculate MACD line (Fast EMA - Slow EMA)
        ema_fast = close_series.ewm(span=fast, adjust=False).mean()
        ema_slow = close_series.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        
        # Calculate Signal line (EMA of MACD)
        if len(macd_line) < signal:
            return None, None, None
        
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        
        # Calculate Histogram (MACD - Signal)
        histogram = macd_line - signal_line
        
        return macd_line.iloc[-1], signal_line.iloc[-1], histogram.iloc[-1]
    
    def on_bar(self, symbol: str, bar: pd.Series) -> None:
        """
        Process each bar for symbol.
        
        Args:
            symbol: Symbol identifier
            bar: OHLCV data with keys ["open", "high", "low", "close", "volume"]
        
        Logic:
        1. Accumulate close prices
        2. Calculate MACD indicators when sufficient data
        3. Detect crossovers (MACD vs Signal)
        4. Apply optional histogram filter
        5. Update position state and emit signals
        """
        # Get or create context for this symbol
        ctx = self.ctx.setdefault(symbol, {
            "closes": [],
            "macd": None,
            "signal": None,
            "histogram": None,
            "prev_macd": None,
            "prev_signal": None,
            "position": 0,
            "last_signal": None,
        })
        
        # Accumulate close prices
        close = float(bar["close"])
        ctx["closes"].append(close)
        
        # Get parameters
        fast = int(self.params.get("fast", 12))
        slow = int(self.params.get("slow", 26))
        signal_period = int(self.params.get("signal", 9))
        use_histogram_filter = bool(self.params.get("use_histogram_filter", True))
        
        # Need enough data for MACD calculation
        min_periods = slow + signal_period
        if len(ctx["closes"]) < min_periods:
            return
        
        # Save previous values for crossover detection
        ctx["prev_macd"] = ctx["macd"]
        ctx["prev_signal"] = ctx["signal"]
        
        # Calculate current MACD values
        macd, signal_line, histogram = self._calculate_macd(
            ctx["closes"], fast, slow, signal_period
        )
        
        if macd is None or signal_line is None:
            return
        
        # Update context
        ctx["macd"] = macd
        ctx["signal"] = signal_line
        ctx["histogram"] = histogram
        
        # Need previous values for crossover detection
        if ctx["prev_macd"] is None or ctx["prev_signal"] is None:
            return
        
        # Detect crossovers
        prev_position = ctx["position"]
        
        # Golden cross: MACD crosses above Signal
        if (ctx["prev_macd"] <= ctx["prev_signal"] and 
            ctx["macd"] > ctx["signal"] and 
            prev_position == 0):
            
            # Optional histogram filter: only buy if histogram is positive or increasing
            if use_histogram_filter and histogram <= 0:
                return
            
            ctx["position"] = 1
            ctx["last_signal"] = "BUY"
            # In production: emit event
            # self.events.put(Event(EventType.STRATEGY_SIGNAL, {
            #     "symbol": symbol,
            #     "action": "BUY",
            #     "price": close,
            #     "macd": macd,
            #     "signal": signal_line,
            #     "histogram": histogram,
            # }))
        
        # Death cross: MACD crosses below Signal
        elif (ctx["prev_macd"] >= ctx["prev_signal"] and 
              ctx["macd"] < ctx["signal"] and 
              prev_position == 1):
            
            # Optional histogram filter: only sell if histogram is negative or decreasing
            if use_histogram_filter and histogram >= 0:
                return
            
            ctx["position"] = 0
            ctx["last_signal"] = "SELL"
            # In production: emit event
            # self.events.put(Event(EventType.STRATEGY_SIGNAL, {
            #     "symbol": symbol,
            #     "action": "SELL",
            #     "price": close,
            #     "macd": macd,
            #     "signal": signal_line,
            #     "histogram": histogram,
            # }))
    
    def on_stop(self) -> None:
        """
        Strategy stops - log summary of final states.
        
        Example:
            for symbol, ctx in self.ctx.items():
                print(f"{symbol}: Position={ctx['position']}, "
                      f"MACD={ctx.get('macd', 0):.4f}, "
                      f"Signal={ctx.get('signal', 0):.4f}, "
                      f"Histogram={ctx.get('histogram', 0):.4f}")
        """
        pass


# Export Backtrader-compatible strategy factory
def build_macd_strategy(**params: Any):
    """
    Factory function to create Backtrader strategy from MACD template.
    
    Args:
        **params: Strategy parameters (e.g., fast=12, slow=26, signal=9)
    
    Returns:
        Backtrader Strategy class
    
    Usage:
        >>> # In strategy_modules.py or backtrader_registry.py
        >>> MACD_TEMPLATE_MODULE = StrategyModule(
        ...     name="macd_template",
        ...     description="MACD crossover using template pattern",
        ...     strategy_cls=build_macd_strategy,  # Factory function
        ...     param_names=["fast", "slow", "signal", "use_histogram_filter"],
        ...     defaults={"fast": 12, "slow": 26, "signal": 9, "use_histogram_filter": True},
        ...     multi_symbol=False,
        ... )
    """
    return build_bt_strategy(MACDTemplate, **params)


# Example usage demonstration
if __name__ == "__main__":
    """
    Demonstration of MACD template usage.
    
    Shows template instantiation and parameter customization.
    """
    import sys
    sys.path.insert(0, "e:/work/Project/stock")
    
    print("MACD Template Strategy Demonstration")
    print("=" * 60)
    
    # Instantiate template
    strategy = MACDTemplate()
    strategy.params = {
        "fast": 12,
        "slow": 26,
        "signal": 9,
        "use_histogram_filter": True,
    }
    
    # Initialize
    strategy.on_init()
    strategy.on_start()
    
    # Simulate some bars (demo data)
    demo_bars = [
        {"close": 100.0},
        {"close": 101.5},
        {"close": 102.0},
        {"close": 101.0},
        {"close": 103.5},
        # ... would need 26+ bars for actual MACD calculation
    ]
    
    print("\nProcessing demo bars:")
    for i, bar_data in enumerate(demo_bars):
        bar = pd.Series(bar_data)
        strategy.on_bar("DEMO.SH", bar)
        print(f"  Bar {i+1}: close={bar_data['close']:.2f}")
    
    # Check context
    ctx = strategy.ctx.get("DEMO.SH", {})
    print(f"\nFinal context:")
    print(f"  Accumulated closes: {len(ctx.get('closes', []))} bars")
    print(f"  MACD: {ctx.get('macd', 'N/A')}")
    print(f"  Signal: {ctx.get('signal', 'N/A')}")
    print(f"  Histogram: {ctx.get('histogram', 'N/A')}")
    print(f"  Position: {ctx.get('position', 0)}")
    print(f"  Last signal: {ctx.get('last_signal', 'None')}")
    
    strategy.on_stop()
    
    print("\n" + "=" * 60)
    print("Template pattern benefits for MACD strategy:")
    print("- Clean separation of indicator calculation")
    print("- Explicit state management (prev values for crossover)")
    print("- Testable in isolation (no Backtrader dependency)")
    print("- Easy to add filters (histogram confirmation)")
    print("- Framework independent (can adapt to any runner)")
