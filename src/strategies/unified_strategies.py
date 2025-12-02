"""
Unified EMA Strategy

A unified EMA crossover strategy that runs on both:
- Backtrader (via BacktraderStrategyAdapter)
- EventEngine (via PaperRunner/LiveRunner)

This demonstrates the "Write Once, Run Anywhere" strategy architecture.

V3.0.0: Initial implementation.

Usage (Backtrader):
    >>> from src.core.strategy_base import BacktraderStrategyAdapter
    >>> bt_cls = BacktraderStrategyAdapter.wrap(UnifiedEMAStrategy, fast=10, slow=30)
    >>> cerebro.addstrategy(bt_cls)

Usage (EventEngine):
    >>> from src.core.paper_runner_v3 import run_paper_v3
    >>> strategy = UnifiedEMAStrategy(fast=10, slow=30)
    >>> result = run_paper_v3(strategy, data_map, events)
"""
from __future__ import annotations

from typing import Optional
from src.core.strategy_base import BaseStrategy
from src.core.interfaces import BarData, StrategyContext


class UnifiedEMAStrategy(BaseStrategy):
    """
    Unified EMA Crossover Strategy.
    
    A classic dual EMA crossover strategy implemented using the unified
    BaseStrategy interface. Works on both Backtrader and EventEngine.
    
    Signals:
    - BUY: Fast EMA crosses above Slow EMA (Golden Cross)
    - SELL: Fast EMA crosses below Slow EMA (Death Cross)
    
    Parameters:
        fast: Fast EMA period (default: 10)
        slow: Slow EMA period (default: 30)
        size: Order size (default: 100)
    
    Example:
        >>> strategy = UnifiedEMAStrategy(fast=10, slow=30, size=100)
        >>> 
        >>> # Backtrader
        >>> bt_cls = BacktraderStrategyAdapter.wrap(UnifiedEMAStrategy, fast=10)
        >>> 
        >>> # EventEngine
        >>> result = run_paper(strategy, data_map, events)
    """
    
    params = {
        "fast": 10,
        "slow": 30,
        "size": 100,
    }
    
    def on_init(self, ctx: StrategyContext) -> None:
        """Initialize strategy state."""
        # State for tracking previous MA values (for crossover detection)
        self.variables["prev_fast"] = {}  # symbol -> prev_fast_ma
        self.variables["prev_slow"] = {}  # symbol -> prev_slow_ma
        
        ctx.log(f"UnifiedEMAStrategy initialized: fast={self.params['fast']}, slow={self.params['slow']}")
    
    def on_start(self, ctx: StrategyContext) -> None:
        """Strategy starts."""
        ctx.log("UnifiedEMAStrategy started")
    
    def on_bar(self, ctx: StrategyContext, bar: BarData) -> None:
        """
        Process each bar - main strategy logic.
        
        Args:
            ctx: Execution context
            bar: Current bar data
        """
        symbol = bar.symbol
        slow_period = self.params["slow"]
        fast_period = self.params["fast"]
        
        # 1. Get historical data
        lookback = slow_period + 5  # Extra buffer
        hist = ctx.history(symbol, ["close"], lookback)
        
        if len(hist) < slow_period:
            # Not enough data
            return
        
        closes = hist["close"]
        
        # 2. Calculate EMAs
        fast_ma = closes.ewm(span=fast_period, adjust=False).mean().iloc[-1]
        slow_ma = closes.ewm(span=slow_period, adjust=False).mean().iloc[-1]
        
        # 3. Get previous values for crossover detection
        prev_fast = self.variables["prev_fast"].get(symbol)
        prev_slow = self.variables["prev_slow"].get(symbol)
        
        # 4. Update state
        self.variables["prev_fast"][symbol] = fast_ma
        self.variables["prev_slow"][symbol] = slow_ma
        
        # 5. Skip first bar (need previous values)
        if prev_fast is None or prev_slow is None:
            return
        
        # 6. Get current position
        pos = ctx.positions.get(symbol)
        current_size = pos.size if pos else 0
        
        # 7. Generate signals
        order_size = self.params["size"]
        
        # Golden Cross: Fast crosses above Slow
        if prev_fast <= prev_slow and fast_ma > slow_ma:
            if current_size <= 0:
                ctx.log(
                    f"Golden Cross: BUY {symbol}",
                    level="info"
                )
                self.buy(ctx, symbol, size=order_size)
        
        # Death Cross: Fast crosses below Slow
        elif prev_fast >= prev_slow and fast_ma < slow_ma:
            if current_size > 0:
                ctx.log(
                    f"Death Cross: SELL {symbol}",
                    level="info"
                )
                self.sell(ctx, symbol, size=current_size)
    
    def on_stop(self, ctx: StrategyContext) -> None:
        """Strategy stops."""
        account = ctx.account
        ctx.log(f"UnifiedEMAStrategy stopped. Final equity: {account.total_value:.2f}")


class UnifiedMACDStrategy(BaseStrategy):
    """
    Unified MACD Strategy.
    
    MACD crossover strategy using the unified interface.
    
    Signals:
    - BUY: MACD crosses above Signal line
    - SELL: MACD crosses below Signal line
    
    Parameters:
        fast: Fast EMA period (default: 12)
        slow: Slow EMA period (default: 26)
        signal: Signal line period (default: 9)
        size: Order size (default: 100)
    """
    
    params = {
        "fast": 12,
        "slow": 26,
        "signal": 9,
        "size": 100,
    }
    
    def on_init(self, ctx: StrategyContext) -> None:
        """Initialize strategy state."""
        self.variables["prev_macd"] = {}
        self.variables["prev_signal"] = {}
        ctx.log("UnifiedMACDStrategy initialized")
    
    def on_start(self, ctx: StrategyContext) -> None:
        """Strategy starts."""
        ctx.log("UnifiedMACDStrategy started")
    
    def on_bar(self, ctx: StrategyContext, bar: BarData) -> None:
        """Process each bar."""
        symbol = bar.symbol
        
        # Need enough data for MACD calculation
        lookback = self.params["slow"] + self.params["signal"] + 10
        hist = ctx.history(symbol, ["close"], lookback)
        
        if len(hist) < lookback - 5:
            return
        
        closes = hist["close"]
        
        # Calculate MACD
        fast_ema = closes.ewm(span=self.params["fast"], adjust=False).mean()
        slow_ema = closes.ewm(span=self.params["slow"], adjust=False).mean()
        macd_line = fast_ema - slow_ema
        signal_line = macd_line.ewm(span=self.params["signal"], adjust=False).mean()
        
        current_macd = macd_line.iloc[-1]
        current_signal = signal_line.iloc[-1]
        
        prev_macd = self.variables["prev_macd"].get(symbol)
        prev_signal = self.variables["prev_signal"].get(symbol)
        
        self.variables["prev_macd"][symbol] = current_macd
        self.variables["prev_signal"][symbol] = current_signal
        
        if prev_macd is None:
            return
        
        pos = ctx.positions.get(symbol)
        current_size = pos.size if pos else 0
        
        # MACD crosses above signal
        if prev_macd <= prev_signal and current_macd > current_signal:
            if current_size <= 0:
                ctx.log(f"MACD Buy Signal: {symbol}")
                self.buy(ctx, symbol, size=self.params["size"])
        
        # MACD crosses below signal
        elif prev_macd >= prev_signal and current_macd < current_signal:
            if current_size > 0:
                ctx.log(f"MACD Sell Signal: {symbol}")
                self.sell(ctx, symbol, size=current_size)
    
    def on_stop(self, ctx: StrategyContext) -> None:
        """Strategy stops."""
        ctx.log("UnifiedMACDStrategy stopped")


class UnifiedBollingerStrategy(BaseStrategy):
    """
    Unified Bollinger Bands Strategy.
    
    Mean reversion strategy using Bollinger Bands.
    
    Signals:
    - BUY: Price touches lower band
    - SELL: Price touches upper band
    
    Parameters:
        period: MA period (default: 20)
        std_dev: Standard deviation multiplier (default: 2.0)
        size: Order size (default: 100)
    """
    
    params = {
        "period": 20,
        "std_dev": 2.0,
        "size": 100,
    }
    
    def on_init(self, ctx: StrategyContext) -> None:
        """Initialize strategy."""
        ctx.log("UnifiedBollingerStrategy initialized")
    
    def on_start(self, ctx: StrategyContext) -> None:
        """Strategy starts."""
        ctx.log("UnifiedBollingerStrategy started")
    
    def on_bar(self, ctx: StrategyContext, bar: BarData) -> None:
        """Process each bar."""
        symbol = bar.symbol
        period = self.params["period"]
        
        hist = ctx.history(symbol, ["close"], period + 5)
        
        if len(hist) < period:
            return
        
        closes = hist["close"]
        
        # Calculate Bollinger Bands
        ma = closes.rolling(period).mean().iloc[-1]
        std = closes.rolling(period).std().iloc[-1]
        
        upper_band = ma + self.params["std_dev"] * std
        lower_band = ma - self.params["std_dev"] * std
        
        current_price = bar.close
        
        pos = ctx.positions.get(symbol)
        current_size = pos.size if pos else 0
        
        # Price below lower band - oversold, buy
        if current_price <= lower_band:
            if current_size <= 0:
                ctx.log(f"Bollinger Buy: {symbol} @ {current_price:.2f} (lower={lower_band:.2f})")
                self.buy(ctx, symbol, size=self.params["size"])
        
        # Price above upper band - overbought, sell
        elif current_price >= upper_band:
            if current_size > 0:
                ctx.log(f"Bollinger Sell: {symbol} @ {current_price:.2f} (upper={upper_band:.2f})")
                self.sell(ctx, symbol, size=current_size)
    
    def on_stop(self, ctx: StrategyContext) -> None:
        """Strategy stops."""
        ctx.log("UnifiedBollingerStrategy stopped")
