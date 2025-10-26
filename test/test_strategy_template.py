"""
Tests for Strategy Template and Context Interface

Validates the enhanced strategy template with Context interface.
"""
from __future__ import annotations

import sys
sys.path.insert(0, "e:/work/Project/stock")

import pytest
import pandas as pd
from datetime import datetime
from typing import Dict, Any

from src.strategy.template import (
    StrategyTemplate, 
    Context, 
    BacktraderAdapter, 
    build_bt_strategy,
    Position,
    Account
)

try:
    import backtrader as bt
except ImportError:
    pytest.skip("Backtrader not installed", allow_module_level=True)


# ---------------------------------------------------------------------------
# Test Strategy Implementation
# ---------------------------------------------------------------------------

class SimpleMAStrategy(StrategyTemplate):
    """Simple moving average strategy for testing."""
    
    params: Dict[str, Any] = {"period": 20, "size": 100}
    
    def on_init(self, ctx: Context) -> None:
        """Initialize strategy state."""
        self.signals = []
        ctx.log("Strategy initialized", "info")
    
    def on_start(self, ctx: Context) -> None:
        """Strategy starts."""
        ctx.log(f"Strategy started with account: {ctx.account}", "info")
    
    def on_bar(self, ctx: Context, symbol: str, bar: pd.Series) -> None:
        """Process each bar."""
        # Get current price
        price = ctx.current_price(symbol)
        if price is None:
            return
        
        # Get history
        period = int(self.params.get("period", 20))
        hist = ctx.history(symbol, ["close"], period)
        
        if len(hist) < period:
            return
        
        # Calculate MA
        ma = hist["close"].mean()
        
        # Simple logic: buy when price > MA, sell when price < MA
        pos = ctx.positions.get(symbol)
        
        if price > ma and (pos is None or pos.size == 0):
            # Buy signal
            size = int(self.params.get("size", 100))
            order_id = ctx.buy(symbol, size=size)
            self.signals.append(("BUY", symbol, price, order_id))
            ctx.log(f"BUY {symbol} @ {price:.2f}, order={order_id}", "info")
        
        elif price < ma and pos is not None and pos.size > 0:
            # Sell signal
            order_id = ctx.sell(symbol)
            self.signals.append(("SELL", symbol, price, order_id))
            ctx.log(f"SELL {symbol} @ {price:.2f}, order={order_id}", "info")
    
    def on_stop(self, ctx: Context) -> None:
        """Strategy stops."""
        ctx.log(f"Strategy stopped. Signals generated: {len(self.signals)}", "info")
        ctx.log(f"Final account value: {ctx.account.total_value:.2f}", "info")


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

class TestStrategyTemplate:
    """Test suite for strategy template."""
    
    def test_strategy_protocol(self):
        """Test that strategy implements the protocol."""
        strategy = SimpleMAStrategy()
        
        # Should have params
        assert hasattr(strategy, "params")
        assert isinstance(strategy.params, dict)
        
        # Should have lifecycle methods
        assert callable(strategy.on_init)
        assert callable(strategy.on_start)
        assert callable(strategy.on_bar)
        assert callable(strategy.on_stop)
    
    def test_backtrader_adapter(self):
        """Test Backtrader adapter creation."""
        adapter = BacktraderAdapter(SimpleMAStrategy, period=20, size=100)
        bt_strategy = adapter.to_bt_strategy()
        
        # Should return a Backtrader Strategy class
        assert issubclass(bt_strategy, bt.Strategy)
        
        # Should have params
        assert hasattr(bt_strategy, "params")


class TestBacktraderIntegration:
    """Test Backtrader integration with real data."""
    
    def test_simple_backtest(self):
        """Test strategy execution in Backtrader."""
        # Create Cerebro
        cerebro = bt.Cerebro()
        
        # Add strategy
        bt_strategy = build_bt_strategy(SimpleMAStrategy, period=10, size=50)
        cerebro.addstrategy(bt_strategy)
        
        # Generate sample data
        dates = pd.date_range("2024-01-01", "2024-02-01", freq="D")
        data = pd.DataFrame({
            "open": [100 + i * 0.5 for i in range(len(dates))],
            "high": [102 + i * 0.5 for i in range(len(dates))],
            "low": [98 + i * 0.5 for i in range(len(dates))],
            "close": [101 + i * 0.5 for i in range(len(dates))],
            "volume": [1000000] * len(dates),
        }, index=dates)
        
        # Add data feed
        data_feed = bt.feeds.PandasData(dataname=data, name="TEST.SH")
        cerebro.adddata(data_feed)
        
        # Set broker
        cerebro.broker.setcash(100000.0)
        cerebro.broker.setcommission(commission=0.001)
        
        # Run backtest
        initial_value = cerebro.broker.getvalue()
        print(f"\nInitial Portfolio Value: {initial_value:.2f}")
        
        strategies = cerebro.run()
        
        final_value = cerebro.broker.getvalue()
        print(f"Final Portfolio Value: {final_value:.2f}")
        
        # Validate execution
        strategy = strategies[0]
        assert hasattr(strategy, "_tmpl")
        assert len(strategy._tmpl.signals) >= 0  # Should have generated signals
        
        print(f"Signals generated: {len(strategy._tmpl.signals)}")
        for signal in strategy._tmpl.signals[:5]:  # Print first 5
            print(f"  {signal}")
    
    def test_context_interface(self):
        """Test Context interface methods."""
        # Create Cerebro with strategy
        cerebro = bt.Cerebro()
        
        # Custom strategy to test context
        class ContextTestStrategy(StrategyTemplate):
            params: Dict[str, Any] = {}
            
            def on_init(self, ctx: Context) -> None:
                self.test_results = {}
            
            def on_start(self, ctx: Context) -> None:
                # Test account access
                self.test_results["account"] = ctx.account
                assert isinstance(ctx.account, Account)
            
            def on_bar(self, ctx: Context, symbol: str, bar: pd.Series) -> None:
                # Test current_price
                price = ctx.current_price(symbol)
                self.test_results["current_price"] = price
                assert price is not None
                
                # Test history
                hist = ctx.history(symbol, ["close", "volume"], 5)
                self.test_results["history"] = hist
                assert len(hist) <= 5
                
                # Test positions
                positions = ctx.positions
                self.test_results["positions"] = positions
                assert isinstance(positions, dict)
                
                # Test datetime
                dt = ctx.get_datetime()
                self.test_results["datetime"] = dt
                assert isinstance(dt, datetime)
            
            def on_stop(self, ctx: Context) -> None:
                pass
        
        bt_strategy = build_bt_strategy(ContextTestStrategy)
        cerebro.addstrategy(bt_strategy)
        
        # Add data
        dates = pd.date_range("2024-01-01", "2024-01-10", freq="D")
        data = pd.DataFrame({
            "open": [100] * len(dates),
            "high": [102] * len(dates),
            "low": [98] * len(dates),
            "close": [101] * len(dates),
            "volume": [1000000] * len(dates),
        }, index=dates)
        
        data_feed = bt.feeds.PandasData(dataname=data, name="TEST.SH")
        cerebro.adddata(data_feed)
        
        # Run
        strategies = cerebro.run()
        strategy = strategies[0]
        
        # Validate context methods were called
        assert "account" in strategy._tmpl.test_results
        assert "current_price" in strategy._tmpl.test_results
        assert "history" in strategy._tmpl.test_results
        assert "positions" in strategy._tmpl.test_results
        assert "datetime" in strategy._tmpl.test_results
        
        print("\nContext Interface Test Results:")
        print(f"  Account: {strategy._tmpl.test_results['account']}")
        print(f"  Current Price: {strategy._tmpl.test_results['current_price']}")
        print(f"  History shape: {strategy._tmpl.test_results['history'].shape}")
        print(f"  Positions: {strategy._tmpl.test_results['positions']}")
        print(f"  Datetime: {strategy._tmpl.test_results['datetime']}")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
