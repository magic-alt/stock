"""
Jupyter/IPython Magic Commands (V5.0-D-4) — Interactive notebook integration.

Provides:
- %quant_backtest — run a backtest inline
- %quant_plot — render ECharts in notebook
- %quant_strategies — list strategies
- %quant_data — load market data as DataFrame
- QuantHelper — programmatic helper class

Usage in Jupyter:
    %load_ext src.notebook.magic
    %quant_strategies
    %quant_backtest --strategy macd --symbols 600519.SH
    df = %quant_data --symbol 600519.SH --start 2024-01-01
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# QuantHelper — non-IPython programmatic API
# ---------------------------------------------------------------------------

class QuantHelper:
    """Helper class for notebook-based quant research.

    Works without IPython installed — pure Python API.
    """

    def __init__(self):
        self._backtest_engine = None

    def list_strategies(self) -> List[str]:
        """List registered strategy names."""
        try:
            from src.strategies.registry import StrategyRegistry
            return sorted(StrategyRegistry.list_strategies())
        except (ImportError, AttributeError):
            return []

    def load_data(
        self,
        symbol: str,
        start: str = "2024-01-01",
        end: str = "2024-12-31",
        provider: str = "akshare",
    ) -> Any:
        """Load OHLCV data as pandas DataFrame."""
        try:
            from src.data_sources.providers import DataPortal
            portal = DataPortal(provider=provider)
            return portal.get_daily(symbol, start, end)
        except Exception as e:
            print(f"Error loading data: {e}")
            return None

    def run_backtest(
        self,
        strategy: str,
        symbols: List[str],
        start: str = "2024-01-01",
        end: str = "2024-12-31",
        cash: float = 100000.0,
        commission: float = 0.001,
    ) -> Any:
        """Run a backtest and return the result."""
        try:
            from src.backtest.engine import BacktestEngine, BacktestConfig
            config = BacktestConfig(
                symbols=symbols,
                start_date=start,
                end_date=end,
                initial_cash=cash,
                commission_rate=commission,
            )
            engine = BacktestEngine(config)
            return engine.run(strategy)
        except Exception as e:
            print(f"Backtest error: {e}")
            return None

    def compute_metrics(self, nav_series) -> Dict[str, float]:
        """Compute performance metrics from a NAV series (numpy array)."""
        try:
            from src.core.vectorized import compute_metrics_fast
            import numpy as np
            arr = np.asarray(nav_series, dtype=np.float64)
            return compute_metrics_fast(arr)
        except ImportError:
            return {"error": "vectorized module not available"}

    def generate_report(self, backtest_result, path: Optional[str] = None) -> str:
        """Generate an HTML report from backtest result."""
        try:
            from src.backtest.report_generator import InteractiveReportGenerator
            gen = InteractiveReportGenerator()
            html = gen.generate(backtest_result)
            if path:
                gen.save(backtest_result, path)
                return f"Report saved to {path}"
            return html
        except Exception as e:
            return f"Report generation error: {e}"


# ---------------------------------------------------------------------------
# IPython Magic Commands
# ---------------------------------------------------------------------------

def _register_magics(ipython):
    """Register magic commands with given IPython instance."""
    from IPython.core.magic import register_line_magic

    helper = QuantHelper()

    @register_line_magic
    def quant_strategies(line):
        """List available strategies."""
        strategies = helper.list_strategies()
        if strategies:
            print(f"Found {len(strategies)} strategies:")
            for s in strategies:
                print(f"  - {s}")
        else:
            print("No strategies available.")
        return strategies

    @register_line_magic
    def quant_data(line):
        """Load market data. Usage: %quant_data --symbol 600519.SH --start 2024-01-01"""
        import shlex
        args = shlex.split(line)
        kwargs = {}
        i = 0
        while i < len(args):
            if args[i].startswith("--") and i + 1 < len(args):
                kwargs[args[i][2:]] = args[i + 1]
                i += 2
            else:
                i += 1
        symbol = kwargs.get("symbol", "600519.SH")
        start = kwargs.get("start", "2024-01-01")
        end = kwargs.get("end", "2024-12-31")
        return helper.load_data(symbol, start, end)

    @register_line_magic
    def quant_backtest(line):
        """Run backtest. Usage: %quant_backtest --strategy macd --symbols 600519.SH"""
        import shlex
        args = shlex.split(line)
        kwargs = {}
        i = 0
        while i < len(args):
            if args[i].startswith("--") and i + 1 < len(args):
                kwargs[args[i][2:]] = args[i + 1]
                i += 2
            else:
                i += 1
        strategy = kwargs.get("strategy", "macd")
        symbols = kwargs.get("symbols", "600519.SH").split(",")
        start = kwargs.get("start", "2024-01-01")
        end = kwargs.get("end", "2024-12-31")
        return helper.run_backtest(strategy, symbols, start, end)


def load_ipython_extension(ipython):
    """Called by %load_ext src.notebook.magic"""
    _register_magics(ipython)
    print("Quant magic commands loaded: %quant_strategies, %quant_data, %quant_backtest")


__all__ = ["QuantHelper", "load_ipython_extension"]
