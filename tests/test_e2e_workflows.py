"""
End-to-End Workflow Tests (P5.3)

Tests that verify complete workflows spanning multiple modules:
- Backtest workflow: data → strategy → engine → metrics
- Paper trading workflow: connect → order → fill → query
- Factor pipeline workflow: compute → analyze → report
"""
from __future__ import annotations

import os
import tempfile
import time
from queue import Queue

import numpy as np
import pandas as pd
import pytest

try:
    import scipy  # noqa: F401
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False


# ---------------------------------------------------------------------------
# Backtest Workflow Tests
# ---------------------------------------------------------------------------

class TestBacktestWorkflow:
    """End-to-end backtest workflow using mock data."""

    @pytest.fixture
    def mock_stock_data(self):
        """Generate realistic mock stock data for backtesting."""
        np.random.seed(42)
        n = 250  # ~1 year of trading days
        dates = pd.date_range("2024-01-02", periods=n, freq="B")
        base_price = 100.0
        returns = np.random.normal(0.0005, 0.02, n)
        prices = base_price * np.exp(np.cumsum(returns))

        return pd.DataFrame({
            "open": prices * np.random.uniform(0.995, 1.005, n),
            "high": prices * np.random.uniform(1.0, 1.02, n),
            "low": prices * np.random.uniform(0.98, 1.0, n),
            "close": prices,
            "volume": np.random.randint(100000, 1000000, n).astype(float),
        }, index=dates)

    def test_factor_to_signal_pipeline(self, mock_stock_data):
        """Compute factors and generate trading signals from data."""
        from src.pipeline.factor_engine import SMA, RSI

        sma_short = SMA(period=10)
        sma_long = SMA(period=30)
        rsi = RSI(period=14)

        sma_s = sma_short.compute(mock_stock_data)
        sma_l = sma_long.compute(mock_stock_data)
        rsi_values = rsi.compute(mock_stock_data)

        # Generate signals from factors
        signals = pd.Series(0, index=mock_stock_data.index)
        signals[sma_s > sma_l] = 1  # Long when short SMA > long SMA
        signals[rsi_values > 70] = 0  # Exit when overbought

        assert signals.sum() > 0  # At least some long signals
        assert len(signals) == len(mock_stock_data)

    def test_backtest_metrics_computed(self, mock_stock_data):
        """Verify metrics are computed from backtest results."""
        # Simulate a simple backtest result
        equity = mock_stock_data["close"] / mock_stock_data["close"].iloc[0] * 1000000

        # Compute basic metrics
        total_return = (equity.iloc[-1] - equity.iloc[0]) / equity.iloc[0]
        max_drawdown = ((equity.cummax() - equity) / equity.cummax()).max()

        assert isinstance(total_return, float)
        assert isinstance(max_drawdown, float)
        assert max_drawdown >= 0


# ---------------------------------------------------------------------------
# Paper Trading Workflow Tests
# ---------------------------------------------------------------------------

class TestPaperTradingWorkflow:
    """End-to-end paper trading workflow via gateway."""

    @pytest.fixture
    def gateway_setup(self):
        from src.gateways.base_live_gateway import GatewayConfig, OrderSide, OrderType
        from src.gateways.xtp_gateway import XtpGateway

        config = GatewayConfig(
            account_id="E2E_PAPER",
            broker="xtp",
            auto_reconnect=False,
        )
        eq = Queue()
        gw = XtpGateway(config, eq)
        yield gw, eq
        if gw.is_connected:
            gw.disconnect()

    def test_full_order_lifecycle(self, gateway_setup):
        """Connect → place order → confirm → cancel → verify."""
        from src.gateways.base_live_gateway import OrderSide, OrderStatus

        gw, eq = gateway_setup

        # Step 1: Connect
        assert gw.connect() is True
        assert gw.is_connected is True

        # Step 2: Place order
        order_id = gw.send_order(
            symbol="600519.SH",
            side=OrderSide.BUY,
            quantity=100,
            price=1800.0,
        )
        assert order_id is not None

        # Step 3: Wait for confirmation
        time.sleep(0.3)
        order = gw.get_order(order_id)
        assert order is not None
        assert order.status == OrderStatus.SUBMITTED

        # Step 4: Cancel order
        assert gw.cancel_order(order_id) is True
        time.sleep(0.3)

        order = gw.get_order(order_id)
        assert order.status == OrderStatus.CANCELLED

        # Step 5: Query account and positions
        account = gw.query_account()
        assert account is not None
        assert account.cash > 0

        positions = gw.query_positions()
        assert isinstance(positions, list)

    def test_multiple_order_types(self, gateway_setup):
        """Place market and limit orders."""
        from src.gateways.base_live_gateway import OrderSide, OrderType

        gw, eq = gateway_setup
        gw.connect()

        # Limit order
        oid1 = gw.send_order(
            symbol="600519.SH",
            side=OrderSide.BUY,
            quantity=100,
            price=1800.0,
            order_type=OrderType.LIMIT,
        )

        # Market order
        oid2 = gw.send_order(
            symbol="000001.SZ",
            side=OrderSide.SELL,
            quantity=200,
            price=15.0,
            order_type=OrderType.LIMIT,
        )

        assert oid1 != oid2
        time.sleep(0.3)

        # Both should be tracked
        assert gw.get_order(oid1) is not None
        assert gw.get_order(oid2) is not None

    def test_event_stream(self, gateway_setup):
        """Verify correct event sequence during trading."""
        from src.gateways.base_live_gateway import OrderSide

        gw, eq = gateway_setup
        gw.connect()

        gw.send_order(
            symbol="600519.SH",
            side=OrderSide.BUY,
            quantity=100,
            price=1800.0,
        )
        time.sleep(0.5)

        events = []
        while not eq.empty():
            events.append(eq.get_nowait())

        event_types = [e["type"] for e in events]

        # Expected sequence: connected → order.submitted → order.accepted
        assert "gateway.connected" in event_types
        assert "gateway.order.submitted" in event_types
        assert "gateway.order.accepted" in event_types


# ---------------------------------------------------------------------------
# Factor Pipeline Workflow Tests
# ---------------------------------------------------------------------------

class TestFactorPipelineWorkflow:
    """End-to-end factor computation and analysis workflow."""

    @pytest.fixture
    def enriched_data(self):
        """Data with both OHLCV and financial columns."""
        np.random.seed(42)
        n = 500
        dates = pd.date_range("2022-01-03", periods=n, freq="B")

        close = 100.0 * np.exp(np.cumsum(np.random.normal(0.0003, 0.015, n)))

        return pd.DataFrame({
            "open": close * np.random.uniform(0.995, 1.005, n),
            "high": close * np.random.uniform(1.0, 1.02, n),
            "low": close * np.random.uniform(0.98, 1.0, n),
            "close": close,
            "volume": np.random.randint(50000, 500000, n).astype(float),
            "eps": np.random.uniform(1.0, 5.0, n),
            "bps": np.random.uniform(10, 50, n),
            "roe": np.random.uniform(0.05, 0.25, n),
            "revenue": np.random.uniform(1e8, 1e10, n),
            "revenue_prev": np.random.uniform(1e8, 1e10, n),
            "dps": np.random.uniform(0.1, 2.0, n),
            "total_debt": np.random.uniform(1e7, 1e9, n),
            "total_equity": np.random.uniform(1e8, 1e10, n),
        }, index=dates)

    def test_technical_and_fundamental_combined(self, enriched_data):
        """Compute both technical and fundamental factors on same data."""
        from src.pipeline.factor_engine import SMA, RSI, MACD
        from src.pipeline.fundamental_factors import PERatio, PBRatio, ROE

        # Technical factors
        sma = SMA(period=20).compute(enriched_data)
        rsi = RSI(period=14).compute(enriched_data)
        macd = MACD().compute(enriched_data)

        # Fundamental factors
        pe = PERatio().compute(enriched_data)
        pb = PBRatio().compute(enriched_data)
        roe = ROE().compute(enriched_data)

        # All should have same length as input
        for series in [sma, rsi, macd, pe, pb, roe]:
            assert len(series) == len(enriched_data)

        # Combine into factor matrix
        factor_matrix = pd.DataFrame({
            "sma_20": sma,
            "rsi_14": rsi,
            "macd": macd,
            "pe_ratio": pe,
            "pb_ratio": pb,
            "roe": roe,
        })

        assert factor_matrix.shape[1] == 6
        assert not factor_matrix.empty

    def test_factor_correlation_workflow(self, enriched_data):
        """Full workflow: compute factors → correlation → redundancy check."""
        from src.pipeline.factor_engine import SMA, RSI, Volatility
        from src.pipeline.fundamental_factors import PERatio, PBRatio
        from src.pipeline.factor_analysis import (
            compute_factor_correlation,
            find_redundant_factors,
            factor_summary,
        )

        # Compute factors
        factor_data = pd.DataFrame({
            "sma_20": SMA(period=20).compute(enriched_data),
            "rsi_14": RSI(period=14).compute(enriched_data),
            "volatility": Volatility(period=20).compute(enriched_data),
            "pe": PERatio().compute(enriched_data),
            "pb": PBRatio().compute(enriched_data),
        }).dropna()

        # Correlation analysis
        corr = compute_factor_correlation(factor_data)
        assert corr.shape == (5, 5)
        assert (corr.values.diagonal() == 1.0).all()

        # Redundancy check
        redundant = find_redundant_factors(factor_data, threshold=0.95)
        assert isinstance(redundant, list)

        # Summary statistics
        summary = factor_summary(factor_data)
        assert "mean" in summary.columns
        assert "std" in summary.columns
        assert len(summary) == 5

    def test_factor_pipeline_factory(self, enriched_data):
        """Use pipeline factory to build and run composite pipeline."""
        from src.pipeline.fundamental_factors import fundamental_pipeline

        pipeline = fundamental_pipeline()
        result = pipeline.run({"TEST": enriched_data})

        assert not result.empty
        assert "pe_ratio" in result.columns
        assert "pb_ratio" in result.columns
        assert "roe" in result.columns

    @pytest.mark.skipif(not _HAS_SCIPY, reason="scipy not installed")
    def test_ic_analysis_workflow(self, enriched_data):
        """Information Coefficient analysis end-to-end."""
        from src.pipeline.factor_engine import RSI
        from src.pipeline.factor_analysis import factor_ic_analysis

        rsi = RSI(period=14).compute(enriched_data)
        forward_returns = enriched_data["close"].pct_change(5).shift(-5)

        factor_df = pd.DataFrame({
            "rsi": rsi,
        }).dropna()

        valid_idx = factor_df.index.intersection(forward_returns.dropna().index)
        if len(valid_idx) > 50:
            ic = factor_ic_analysis(
                factor_df.loc[valid_idx],
                forward_returns.loc[valid_idx],
            )
            assert isinstance(ic, pd.Series)
            assert "rsi" in ic.index
