"""
Pipeline-to-Backtest Bridge

Bridges the factor-engine :class:`~src.pipeline.factor_engine.Pipeline` with
the :class:`~src.backtest.engine.BacktestEngine`, enabling factor-augmented
backtests without modifying either subsystem.

Components
----------
``pipeline_to_backtest_data``
    Merges pipeline factor columns into price DataFrames that Backtrader
    can consume via :class:`GenericPandasData`.

``FundamentalFactorFeed``
    Wraps fundamental-factor DataFrames into a Backtrader-friendly format.

``run_pipeline_backtest``
    End-to-end convenience function: run a pipeline for a set of symbols,
    merge the factor output into price data, and execute a backtest.

Usage::

    from src.pipeline.factor_engine import Pipeline, Momentum, RSI
    from src.pipeline.backtest_bridge import run_pipeline_backtest

    pipeline = Pipeline()
    pipeline.add("mom_20", Momentum(20))
    pipeline.add("rsi_14", RSI(14))

    result = run_pipeline_backtest(
        symbols=["600519.SH"],
        pipeline=pipeline,
        start="2024-01-01",
        end="2024-06-30",
    )
    print(result["metrics"])
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pipeline result -> Backtrader data adapter
# ---------------------------------------------------------------------------

def pipeline_to_backtest_data(
    pipeline_result: pd.DataFrame,
    price_data: Dict[str, pd.DataFrame],
    factor_columns: Optional[List[str]] = None,
) -> Dict[str, pd.DataFrame]:
    """Merge pipeline factor values into per-symbol price DataFrames.

    Args:
        pipeline_result: DataFrame returned by :meth:`Pipeline.run`.  May
            be a flat DataFrame (one row per date, columns = factor names)
            or a wide DataFrame whose columns are ``(factor, symbol)``
            tuples.
        price_data: Mapping ``{symbol: OHLCV DataFrame}``.
        factor_columns: Explicit list of factor column names to merge.
            When ``None``, all non-OHLCV columns found in *pipeline_result*
            are merged.

    Returns:
        A new ``{symbol: DataFrame}`` mapping where each DataFrame contains
        the original OHLCV columns **plus** the factor columns aligned on
        the date index.
    """
    if pipeline_result is None or pipeline_result.empty:
        return {sym: df.copy() for sym, df in price_data.items()}

    merged: Dict[str, pd.DataFrame] = {}

    for symbol, price_df in price_data.items():
        enriched = price_df.copy()

        # Determine which columns from the pipeline belong to this symbol
        if isinstance(pipeline_result.columns, pd.MultiIndex):
            # Wide format: columns are (field, symbol)
            try:
                sym_slice = pipeline_result.xs(symbol, axis=1, level=1)
            except KeyError:
                sym_slice = pd.DataFrame(index=pipeline_result.index)
        else:
            # Flat format: one factor per column (single-symbol pipeline)
            sym_slice = pipeline_result

        # Filter to requested factor columns
        cols_to_add = factor_columns or [
            c for c in sym_slice.columns
            if c.lower() not in {"open", "high", "low", "close", "volume"}
        ]
        available = [c for c in cols_to_add if c in sym_slice.columns]

        if available:
            factor_df = sym_slice[available]
            # Align on index (date)
            factor_df = factor_df.reindex(enriched.index)
            for col in available:
                enriched[col] = factor_df[col]

        merged[symbol] = enriched

    return merged


# ---------------------------------------------------------------------------
# FundamentalFactorFeed
# ---------------------------------------------------------------------------

class FundamentalFactorFeed:
    """Wrap fundamental factor data into a Backtrader-compatible format.

    Stores one DataFrame per symbol with canonical financial columns
    (``eps``, ``bps``, ``roe``, ``revenue``, ``dps``, etc.) aligned to a
    ``DatetimeIndex`` that matches the price data timeline.

    Usage::

        feed = FundamentalFactorFeed(financial_data)
        bt_feed = feed.to_backtrader_feed()
        cerebro.adddata(bt_feed, name="fundamentals")
    """

    def __init__(self, financial_data: Dict[str, pd.DataFrame]) -> None:
        """
        Args:
            financial_data: ``{symbol: DataFrame}`` where each DataFrame
                has a ``DatetimeIndex`` and financial columns such as
                ``eps``, ``bps``, ``roe``, ``revenue``, ``dps``.
        """
        self._data: Dict[str, pd.DataFrame] = {}
        for symbol, df in financial_data.items():
            if df is not None and not df.empty:
                self._data[symbol] = df.sort_index()

    @property
    def symbols(self) -> List[str]:
        return list(self._data.keys())

    def get(self, symbol: str) -> Optional[pd.DataFrame]:
        return self._data.get(symbol)

    def merged_frame(self, symbol: str, price_df: pd.DataFrame) -> pd.DataFrame:
        """Merge fundamental data onto a price DataFrame for a single symbol.

        Missing financial values on non-report dates are forward-filled.
        """
        fund = self._data.get(symbol)
        if fund is None or fund.empty:
            return price_df.copy()

        merged = price_df.copy()
        for col in fund.columns:
            if col in merged.columns:
                continue
            series = fund[col].reindex(merged.index, method="ffill")
            merged[col] = series
        return merged

    def to_backtrader_feed(self, symbol: Optional[str] = None) -> Any:
        """Return a Backtrader PandasData feed for the first (or given) symbol.

        This is a convenience helper; for multi-symbol backtests call
        :meth:`merged_frame` and build feeds manually.
        """
        try:
            import backtrader as bt
        except ImportError:
            raise ImportError("backtrader is required for to_backtrader_feed()")

        sym = symbol or (self.symbols[0] if self.symbols else None)
        if sym is None:
            raise ValueError("No fundamental data loaded")

        df = self._data.get(sym)
        if df is None or df.empty:
            raise ValueError(f"No fundamental data for {sym}")

        # Ensure standard OHLCV columns exist (fill with NaN if absent)
        for col in ("open", "high", "low", "close", "volume"):
            if col not in df.columns:
                df[col] = np.nan

        feed_df = df[["open", "high", "low", "close", "volume"]].copy()
        feed_df.index = pd.to_datetime(feed_df.index)
        feed_df.index.name = "datetime"

        from src.backtest.strategy_modules import GenericPandasData
        return GenericPandasData(dataname=feed_df)


# ---------------------------------------------------------------------------
# Convenience: end-to-end pipeline backtest
# ---------------------------------------------------------------------------

def run_pipeline_backtest(
    symbols: List[str],
    pipeline: Any,
    start: str = "2024-01-01",
    end: str = "2024-12-31",
    strategy: str = "ema",
    strategy_params: Optional[Dict[str, Any]] = None,
    *,
    source: str = "akshare",
    benchmark: Optional[str] = "000300.SH",
    cash: float = 200_000.0,
    commission: float = 0.001,
    slippage: float = 0.001,
    price_data: Optional[Dict[str, pd.DataFrame]] = None,
) -> Dict[str, Any]:
    """Run a factor pipeline and feed augmented data into a backtest.

    This is the highest-level convenience function.  It:

    1. Loads price data (or uses the provided *price_data*).
    2. Runs the factor ``pipeline`` on the data.
    3. Merges factor columns into the price DataFrames.
    4. Runs a backtest with the specified strategy.

    Args:
        symbols: List of stock symbols.
        pipeline: A :class:`~src.pipeline.factor_engine.Pipeline` instance.
        start: Inclusive start date (YYYY-MM-DD).
        end: Inclusive end date (YYYY-MM-DD).
        strategy: Strategy name registered in the BacktestEngine STRATEGY_REGISTRY.
        strategy_params: Optional strategy parameter overrides.
        source: Data provider name.
        benchmark: Benchmark index code (or ``None``).
        cash: Starting capital.
        commission: Commission rate.
        slippage: Slippage factor.
        price_data: Pre-loaded price data (skips data download when provided).

    Returns:
        Dict with ``nav``, ``metrics``, ``factor_result``, and ``data_map``.
    """
    from src.backtest.engine import BacktestEngine

    engine = BacktestEngine(source=source)

    # Step 1: load price data
    if price_data is not None:
        data_map = price_data
    else:
        data_map = engine._load_data(symbols, start, end)

    if not data_map:
        logger.warning("run_pipeline_backtest: no price data loaded")
        return {
            "nav": pd.Series(dtype=float),
            "metrics": {},
            "factor_result": pd.DataFrame(),
            "data_map": {},
        }

    # Step 2: run the factor pipeline
    factor_result = pipeline.run(data_map) if pipeline else pd.DataFrame()

    # Step 3: merge factor columns into price data
    augmented = pipeline_to_backtest_data(factor_result, data_map)

    # Step 4: run backtest
    bench_nav = engine._load_benchmark(benchmark, start, end) if benchmark else None
    params = strategy_params or {}

    from src.backtest.strategy_modules import STRATEGY_REGISTRY
    module = STRATEGY_REGISTRY.get(strategy)
    if module is None:
        raise KeyError(f"Unknown strategy: {strategy}")

    param_dict = module.coerce(params)
    nav, metrics, _ = engine._execute_strategy(
        module,
        augmented,
        param_dict,
        cash=cash,
        commission=commission,
        slippage=slippage,
        benchmark_nav=bench_nav,
    )

    return {
        "nav": nav,
        "metrics": metrics,
        "factor_result": factor_result,
        "data_map": augmented,
    }


__all__ = [
    "pipeline_to_backtest_data",
    "FundamentalFactorFeed",
    "run_pipeline_backtest",
]
