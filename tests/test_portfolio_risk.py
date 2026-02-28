"""
Comprehensive tests for PortfolioManager (src/core/portfolio.py).

Uses only standard library + numpy + pandas with synthetic NAV series.
No external broker connections or mocks required.
"""
from __future__ import annotations

import inspect

import numpy as np
import pandas as pd
import pytest

from src.core.portfolio import AllocationResult, PortfolioManager


# ---------------------------------------------------------------------------
# Synthetic NAV helpers
# ---------------------------------------------------------------------------

def _make_nav(seed: int, n: int = 252, daily_vol: float = 0.01) -> pd.Series:
    np.random.seed(seed)
    returns = np.random.randn(n) * daily_vol
    nav = pd.Series(
        (1 + returns).cumprod(),
        index=pd.date_range("2023-01-01", periods=n),
    )
    return nav


def _make_pm_3strats() -> PortfolioManager:
    """Return a PortfolioManager with 3 synthetic strategies."""
    pm = PortfolioManager(risk_free_rate=0.02, rebalance_days=21)
    np.random.seed(42)
    nav1 = pd.Series(
        (1 + np.random.randn(252) * 0.01).cumprod(),
        index=pd.date_range("2023-01-01", periods=252),
    )
    np.random.seed(7)
    nav2 = pd.Series(
        (1 + np.random.randn(252) * 0.015).cumprod(),
        index=pd.date_range("2023-01-01", periods=252),
    )
    np.random.seed(99)
    nav3 = pd.Series(
        (1 + np.random.randn(252) * 0.008).cumprod(),
        index=pd.date_range("2023-01-01", periods=252),
    )
    pm.add_strategy("s1", nav1)
    pm.add_strategy("s2", nav2)
    pm.add_strategy("s3", nav3)
    return pm


# ---------------------------------------------------------------------------
# Tests: add / remove strategy
# ---------------------------------------------------------------------------

class TestAddRemoveStrategy:
    def test_add_strategy_and_count(self):
        pm = PortfolioManager()
        pm.add_strategy("s1", _make_nav(1))
        assert "s1" in pm._strategies  # noqa: SLF001

    def test_remove_strategy(self):
        pm = PortfolioManager()
        pm.add_strategy("s1", _make_nav(1))
        pm.remove_strategy("s1")
        assert "s1" not in pm._strategies  # noqa: SLF001

    def test_remove_nonexistent_is_noop(self):
        pm = PortfolioManager()
        pm.remove_strategy("does_not_exist")  # should not raise

    def test_add_with_risk_config_accepted(self):
        pm = PortfolioManager()
        pm.add_strategy("s1", _make_nav(1), risk_config={"max_dd": 0.2})
        assert "s1" in pm._strategies  # noqa: SLF001


# ---------------------------------------------------------------------------
# Tests: covariance matrix
# ---------------------------------------------------------------------------

class TestCovarianceMatrix:
    def test_covariance_matrix_shape(self):
        pm = _make_pm_3strats()
        cov = pm.compute_covariance()
        assert cov.shape == (3, 3)

    def test_covariance_is_symmetric(self):
        pm = _make_pm_3strats()
        cov = pm.compute_covariance()
        np.testing.assert_allclose(cov.values, cov.values.T, atol=1e-10)

    def test_covariance_diagonal_positive(self):
        pm = _make_pm_3strats()
        cov = pm.compute_covariance()
        assert all(cov.values[i, i] > 0 for i in range(3))

    def test_covariance_requires_2_strategies(self):
        pm = PortfolioManager()
        pm.add_strategy("only", _make_nav(1))
        with pytest.raises(ValueError, match="at least 2"):
            pm.compute_covariance()

    def test_covariance_column_names_match_strategy_ids(self):
        pm = _make_pm_3strats()
        cov = pm.compute_covariance()
        assert set(cov.columns) == {"s1", "s2", "s3"}


# ---------------------------------------------------------------------------
# Tests: sharpe weight optimisation
# ---------------------------------------------------------------------------

class TestOptimizeWeightsSharpe:
    def test_optimize_sharpe_weights_sum_to_one(self):
        pm = _make_pm_3strats()
        result = pm.optimize_weights(objective="sharpe", max_weight=0.6, step=0.1)
        total = sum(result.weights.values())
        assert abs(total - 1.0) < 1e-6

    def test_add_strategy_and_compute_weights(self):
        pm = _make_pm_3strats()
        result = pm.optimize_weights(objective="sharpe", max_weight=0.6, step=0.1)
        assert isinstance(result, AllocationResult)
        assert len(result.weights) == 3
        total = sum(result.weights.values())
        assert abs(total - 1.0) < 1e-6

    def test_optimize_sharpe_returns_allocation_result(self):
        pm = _make_pm_3strats()
        result = pm.optimize_weights(objective="sharpe", max_weight=0.6, step=0.1)
        assert isinstance(result.portfolio_sharpe, float)
        assert isinstance(result.portfolio_vol, float)
        assert isinstance(result.expected_return, float)

    def test_optimize_sharpe_correlation_matrix_populated(self):
        pm = _make_pm_3strats()
        result = pm.optimize_weights(objective="sharpe", max_weight=0.6, step=0.1)
        assert not result.correlation_matrix.empty
        assert result.correlation_matrix.shape == (3, 3)

    def test_optimize_sharpe_all_weights_nonnegative(self):
        pm = _make_pm_3strats()
        result = pm.optimize_weights(objective="sharpe", max_weight=0.6, step=0.1)
        for sid, w in result.weights.items():
            assert w >= 0.0, f"Negative weight for {sid}: {w}"


# ---------------------------------------------------------------------------
# Tests: min-vol / drawdown / return objectives
# ---------------------------------------------------------------------------

class TestOptimizeWeightsMinVol:
    def test_optimize_min_vol(self):
        # combo_optimizer maps 'drawdown' objective to least-negative max drawdown
        pm = _make_pm_3strats()
        result = pm.optimize_weights(objective="drawdown", max_weight=0.6, step=0.1)
        total = sum(result.weights.values())
        assert abs(total - 1.0) < 1e-6

    def test_optimize_return_objective(self):
        pm = _make_pm_3strats()
        result = pm.optimize_weights(objective="return", max_weight=0.6, step=0.1)
        total = sum(result.weights.values())
        assert abs(total - 1.0) < 1e-6


# ---------------------------------------------------------------------------
# Tests: max-weight constraint
# ---------------------------------------------------------------------------

class TestMaxWeightConstraint:
    def test_max_weight_constraint_respected(self):
        pm = _make_pm_3strats()
        max_w = 0.5
        result = pm.optimize_weights(objective="sharpe", max_weight=max_w, step=0.1)
        for sid, w in result.weights.items():
            assert w <= max_w + 1e-9, f"Strategy {sid} weight {w} exceeds max {max_w}"

    def test_max_single_strategy_weight_field_correct(self):
        pm = _make_pm_3strats()
        max_w = 0.5
        result = pm.optimize_weights(objective="sharpe", max_weight=max_w, step=0.1)
        expected_max = max(result.weights.values())
        assert abs(result.max_single_strategy_weight - expected_max) < 1e-9


# ---------------------------------------------------------------------------
# Tests: equal risk parity
# ---------------------------------------------------------------------------

class TestEqualRiskParity:
    def test_equal_risk_parity_weights(self):
        pm = _make_pm_3strats()
        result = pm.optimize_weights(objective="equal_risk", max_weight=0.4)
        total = sum(result.weights.values())
        assert abs(total - 1.0) < 1e-9

    def test_equal_risk_max_weight_respected(self):
        pm = _make_pm_3strats()
        max_w = 0.4
        result = pm.optimize_weights(objective="equal_risk", max_weight=max_w)
        for sid, w in result.weights.items():
            assert w <= max_w + 1e-9

    def test_equal_risk_higher_vol_gets_lower_weight(self):
        """Strategy with more volatility should receive lower weight under risk parity."""
        pm = PortfolioManager()
        np.random.seed(0)
        low_vol = pd.Series(
            (1 + np.random.randn(252) * 0.005).cumprod(),
            index=pd.date_range("2023-01-01", periods=252),
        )
        np.random.seed(1)
        high_vol = pd.Series(
            (1 + np.random.randn(252) * 0.03).cumprod(),
            index=pd.date_range("2023-01-01", periods=252),
        )
        pm.add_strategy("low_vol", low_vol)
        pm.add_strategy("high_vol", high_vol)
        result = pm.optimize_weights(objective="equal_risk", max_weight=1.0)
        assert result.weights["low_vol"] >= result.weights["high_vol"]

    def test_equal_risk_returns_zero_sharpe_and_vol(self):
        pm = _make_pm_3strats()
        result = pm.optimize_weights(objective="equal_risk", max_weight=0.4)
        assert result.portfolio_sharpe == 0.0
        assert result.portfolio_vol == 0.0
        assert result.expected_return == 0.0


# ---------------------------------------------------------------------------
# Tests: aggregate risk
# ---------------------------------------------------------------------------

class TestAggregateRisk:
    def test_aggregate_risk_returns_dict(self):
        pm = _make_pm_3strats()
        account_values = {"s1": 100_000.0, "s2": 150_000.0, "s3": 50_000.0}
        risk = pm.aggregate_risk(account_values)
        assert isinstance(risk, dict)
        assert len(risk) > 0

    def test_aggregate_risk_var(self):
        """VaR at 95% should be negative (loss-side quantile)."""
        pm = _make_pm_3strats()
        account_values = {"s1": 100_000.0, "s2": 100_000.0, "s3": 100_000.0}
        risk = pm.aggregate_risk(account_values)
        assert "var_95" in risk
        assert risk["var_95"] < 0.0

    def test_aggregate_risk_portfolio_drawdown(self):
        """max_drawdown must be between 0 and 1."""
        pm = _make_pm_3strats()
        account_values = {"s1": 100_000.0, "s2": 100_000.0, "s3": 100_000.0}
        risk = pm.aggregate_risk(account_values)
        assert 0.0 <= risk["max_drawdown"] <= 1.0

    def test_aggregate_risk_total_value(self):
        pm = _make_pm_3strats()
        account_values = {"s1": 100_000.0, "s2": 200_000.0, "s3": 50_000.0}
        risk = pm.aggregate_risk(account_values)
        assert risk["total_value"] == pytest.approx(350_000.0)

    def test_aggregate_risk_weights_sum_to_one(self):
        pm = _make_pm_3strats()
        account_values = {"s1": 100_000.0, "s2": 200_000.0, "s3": 50_000.0}
        risk = pm.aggregate_risk(account_values)
        assert abs(sum(risk["weights"].values()) - 1.0) < 1e-9

    def test_aggregate_risk_hhi_bounds(self):
        """Equal weights across 3 strategies → HHI = 1/3."""
        pm = _make_pm_3strats()
        account_values = {"s1": 100_000.0, "s2": 100_000.0, "s3": 100_000.0}
        risk = pm.aggregate_risk(account_values)
        n = 3
        assert risk["hhi_concentration"] == pytest.approx(1.0 / n, rel=1e-6)

    def test_aggregate_risk_zero_total_returns_empty(self):
        pm = _make_pm_3strats()
        risk = pm.aggregate_risk({"s1": 0.0, "s2": 0.0})
        assert risk == {}

    def test_aggregate_risk_es_lte_var(self):
        """Expected Shortfall (ES) must be <= VaR (deeper tail)."""
        pm = _make_pm_3strats()
        account_values = {"s1": 100_000.0, "s2": 100_000.0, "s3": 100_000.0}
        risk = pm.aggregate_risk(account_values)
        assert risk["es_95"] <= risk["var_95"] + 1e-9

    def test_aggregate_risk_num_strategies_field(self):
        pm = _make_pm_3strats()
        account_values = {"s1": 100_000.0, "s2": 100_000.0, "s3": 100_000.0}
        risk = pm.aggregate_risk(account_values)
        assert risk["num_strategies"] == 3


# ---------------------------------------------------------------------------
# Tests: rebalance detection
# ---------------------------------------------------------------------------

class TestRebalanceDetection:
    def test_rebalance_needed_detects_drift(self):
        pm = PortfolioManager()
        current = {"s1": 0.5, "s2": 0.5}
        target = {"s1": 0.4, "s2": 0.6}
        # drift = 0.1 > threshold 0.05
        assert pm.check_rebalance_needed(current, target, threshold=0.05) is True

    def test_rebalance_not_needed_within_threshold(self):
        pm = PortfolioManager()
        current = {"s1": 0.42, "s2": 0.58}
        target = {"s1": 0.40, "s2": 0.60}
        # drift = 0.02 < threshold 0.05
        assert pm.check_rebalance_needed(current, target, threshold=0.05) is False

    def test_rebalance_none_target_always_false(self):
        pm = PortfolioManager()
        current = {"s1": 0.9, "s2": 0.1}
        assert pm.check_rebalance_needed(current, target_weights=None) is False

    def test_rebalance_exact_threshold_not_triggered(self):
        pm = PortfolioManager()
        current = {"s1": 0.45, "s2": 0.55}
        target = {"s1": 0.40, "s2": 0.60}
        # drift = exactly 0.05, threshold = 0.05 → NOT triggered (strict >)
        assert pm.check_rebalance_needed(current, target, threshold=0.05) is False

    def test_rebalance_needed_missing_strategy_in_current(self):
        pm = PortfolioManager()
        # current has no s2 entry → treated as 0.0, target has 0.4 → drift = 0.4
        current = {"s1": 0.6}
        target = {"s1": 0.5, "s2": 0.4}  # s2 missing from current → drift = 0.4
        assert pm.check_rebalance_needed(current, target, threshold=0.05) is True


# ---------------------------------------------------------------------------
# Tests: rebalance orders
# ---------------------------------------------------------------------------

class TestRebalanceOrders:
    def test_get_rebalance_orders(self):
        pm = PortfolioManager()
        current = {"s1": 0.3, "s2": 0.7}
        target = {"s1": 0.5, "s2": 0.5}
        orders = pm.get_rebalance_orders(current, target, account_value=100_000.0)
        assert len(orders) == 2
        s1_order = next(o for o in orders if o["strategy_id"] == "s1")
        s2_order = next(o for o in orders if o["strategy_id"] == "s2")
        assert s1_order["direction"] == "increase"
        assert s2_order["direction"] == "decrease"

    def test_get_rebalance_orders_delta_values(self):
        pm = PortfolioManager()
        current = {"s1": 0.3, "s2": 0.7}
        target = {"s1": 0.5, "s2": 0.5}
        orders = pm.get_rebalance_orders(current, target, account_value=100_000.0)
        s1_order = next(o for o in orders if o["strategy_id"] == "s1")
        # delta = (0.5 - 0.3) * 100_000 = 20_000
        assert s1_order["delta_value"] == pytest.approx(20_000.0)

    def test_get_rebalance_orders_small_delta_filtered(self):
        """Deltas below 0.01 should produce no orders."""
        pm = PortfolioManager()
        current = {"s1": 0.5001, "s2": 0.4999}
        target = {"s1": 0.5000, "s2": 0.5000}
        orders = pm.get_rebalance_orders(current, target, account_value=1.0)
        assert len(orders) == 0

    def test_get_rebalance_orders_new_strategy(self):
        """Strategy absent from current but in target gets an 'increase' order."""
        pm = PortfolioManager()
        current = {"s1": 1.0}
        target = {"s1": 0.5, "s2": 0.5}
        orders = pm.get_rebalance_orders(current, target, account_value=100_000.0)
        s2_order = next((o for o in orders if o["strategy_id"] == "s2"), None)
        assert s2_order is not None
        assert s2_order["direction"] == "increase"

    def test_get_rebalance_orders_contains_weight_fields(self):
        pm = PortfolioManager()
        current = {"s1": 0.4, "s2": 0.6}
        target = {"s1": 0.5, "s2": 0.5}
        orders = pm.get_rebalance_orders(current, target, account_value=50_000.0)
        for order in orders:
            assert "current_weight" in order
            assert "target_weight" in order
            assert "strategy_id" in order
            assert "delta_value" in order
            assert "direction" in order


# ---------------------------------------------------------------------------
# Tests: integration with combo_optimizer
# ---------------------------------------------------------------------------

class TestComboOptimizerIntegration:
    def test_covariance_constrained_optimization(self):
        """
        Check whether optimize_portfolio accepts cov_matrix / max_portfolio_vol.
        These parameters do not currently exist; the test is skipped.
        """
        from src.optimizer.combo_optimizer import optimize_portfolio  # noqa: PLC0415
        sig = inspect.signature(optimize_portfolio)
        params = sig.parameters
        if "cov_matrix" not in params or "max_portfolio_vol" not in params:
            pytest.skip(
                "optimize_portfolio does not support cov_matrix/max_portfolio_vol params"
            )
        # Reached only when params are present
        pm = _make_pm_3strats()
        cov = pm.compute_covariance()
        result = optimize_portfolio(
            nav_map=dict(pm._strategies),  # noqa: SLF001
            step=0.1,
            objective="sharpe",
            max_weight=0.6,
            cov_matrix=cov,
            max_portfolio_vol=0.2,
        )
        assert result is not None

    def test_fallback_when_no_cov_matrix(self):
        """optimize_portfolio works correctly without cov_matrix (standard API)."""
        from src.optimizer.combo_optimizer import optimize_portfolio  # noqa: PLC0415
        pm = _make_pm_3strats()
        result = optimize_portfolio(
            nav_map=dict(pm._strategies),  # noqa: SLF001
            step=0.1,
            objective="sharpe",
            max_weight=0.6,
            risk_free=0.02,
        )
        assert result is not None
        total = sum(result.weights.values())
        assert abs(total - 1.0) < 1e-6

    def test_optimize_portfolio_single_strategy_raises_or_succeeds(self):
        """Single strategy: weight == 1.0 or RuntimeError for infeasible grid."""
        from src.optimizer.combo_optimizer import optimize_portfolio  # noqa: PLC0415
        nav = _make_nav(42)
        try:
            result = optimize_portfolio(
                nav_map={"s1": nav},
                step=0.5,
                objective="sharpe",
                max_weight=1.0,
            )
            assert result.weights["s1"] == pytest.approx(1.0)
        except RuntimeError:
            pass  # acceptable


# ---------------------------------------------------------------------------
# Tests: edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_optimize_weights_no_strategies_raises(self):
        pm = PortfolioManager()
        with pytest.raises(ValueError, match="No strategies added"):
            pm.optimize_weights()

    def test_portfolio_vol_computed_for_two_strategies(self):
        pm = PortfolioManager()
        pm.add_strategy("s1", _make_nav(10))
        pm.add_strategy("s2", _make_nav(20))
        result = pm.optimize_weights(objective="sharpe", max_weight=1.0, step=0.5)
        assert result.portfolio_vol >= 0.0

    def test_aggregate_risk_no_strategies_returns_empty(self):
        pm = PortfolioManager()
        risk = pm.aggregate_risk({"s1": 100_000.0})
        # No strategies registered → all_rets will be empty
        assert risk == {}

    def test_portfolio_manager_default_params(self):
        pm = PortfolioManager()
        assert pm._risk_free_rate == 0.02  # noqa: SLF001
        assert pm._rebalance_days == 21  # noqa: SLF001
