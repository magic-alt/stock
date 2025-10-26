"""
Strategy Template Protocol and Backtrader Adapter

Provides a simplified, framework-independent strategy development interface.
Strategies implementing StrategyTemplate can be adapted to Backtrader or custom runners.
"""
from __future__ import annotations

from typing import Protocol, Dict, Any, Type
import pandas as pd

try:
    import backtrader as bt
except ImportError as exc:
    raise ImportError("backtrader is required: pip install backtrader") from exc


class StrategyTemplate(Protocol):
    """
    Simplified strategy protocol decoupled from execution engine.
    
    Lifecycle methods:
    - on_init(): Initialize indicators and state (called once before data)
    - on_start(): Strategy starts (called once after data loaded)
    - on_bar(symbol, bar): Process each bar (called for every symbol/bar)
    - on_stop(): Strategy stops (called once after all bars processed)
    
    State management:
    - self.params: Dict[str, Any] - Strategy parameters
    - self.ctx: Dict[str, Any] - Per-symbol context (user-defined)
    
    Example:
        >>> class MyStrategy(StrategyTemplate):
        ...     params = {"period": 20}
        ...     
        ...     def on_init(self):
        ...         self.ctx = {}
        ...     
        ...     def on_bar(self, symbol: str, bar: pd.Series):
        ...         # Access: bar["open"], bar["close"], etc.
        ...         # Emit signals via events or store in self.ctx
        ...         pass
    """
    
    params: Dict[str, Any]
    
    def on_init(self) -> None:
        """
        Initialize indicators and state.
        
        Called once before any data is processed.
        Use this to set up:
        - Per-symbol context dictionaries
        - Indicator buffers
        - Internal state
        """
        ...
    
    def on_start(self) -> None:
        """
        Strategy starts.
        
        Called once after data is loaded but before first bar.
        Use this for:
        - Initial setup that requires data knowledge
        - Pre-computation
        """
        ...
    
    def on_bar(self, symbol: str, bar: pd.Series) -> None:
        """
        Process each bar.
        
        Called for every symbol on every bar.
        
        Args:
            symbol: Symbol identifier (e.g., "600519.SH")
            bar: OHLCV data as pd.Series with keys:
                 ["open", "high", "low", "close", "volume"]
        
        Use this to:
        - Update indicators
        - Generate signals
        - Emit events (strategy.signal)
        - Store state in self.ctx
        """
        ...
    
    def on_stop(self) -> None:
        """
        Strategy stops.
        
        Called once after all bars are processed.
        Use this for:
        - Cleanup
        - Final calculations
        - Logging summary
        """
        ...


class BacktraderAdapter:
    """
    Adapts StrategyTemplate to Backtrader.Strategy.
    
    Bridges the simplified template interface to Backtrader's execution model.
    
    Usage:
        >>> adapter = BacktraderAdapter(MyTemplateStrategy, period=20, threshold=0.02)
        >>> bt_strategy = adapter.to_bt_strategy()
        >>> cerebro.addstrategy(bt_strategy)
    
    Features:
    - Automatic lifecycle mapping (on_init -> __init__, on_bar -> next, etc.)
    - Parameter passing from kwargs to template.params
    - Multi-symbol support via data name tracking
    - Bar data conversion (Backtrader lines -> pandas Series)
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
                
                # Map data feeds to symbol names
                self._names: Dict[str, Any] = {}
                for i, data in enumerate(self.datas):
                    name = getattr(data, '_name', None) or f"symbol_{i}"
                    self._names[name] = data
                
                # Call template init
                self._tmpl.on_init()
            
            def start(self):
                """
                Strategy starts.
                
                Lifecycle: Backtrader start() -> Template on_start()
                """
                self._tmpl.on_start()
            
            def next(self):
                """
                Process each bar.
                
                Lifecycle: Backtrader next() -> Template on_bar(symbol, bar)
                
                Called once per bar for the synchronized data feeds.
                Converts Backtrader's line notation to pandas Series.
                """
                for name, data in self._names.items():
                    # Convert Backtrader data lines to pandas Series
                    bar = pd.Series({
                        "open": float(data.open[0]),
                        "high": float(data.high[0]),
                        "low": float(data.low[0]),
                        "close": float(data.close[0]),
                        "volume": float(getattr(data, "volume", [0])[0]),
                    })
                    
                    # Call template's bar handler
                    self._tmpl.on_bar(name, bar)
            
            def stop(self):
                """
                Strategy stops.
                
                Lifecycle: Backtrader stop() -> Template on_stop()
                """
                self._tmpl.on_stop()
        
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
