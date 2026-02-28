"""
Portfolio capital allocation and risk aggregation for multi-strategy trading.

Provides weight optimization, covariance computation, risk parity allocation,
drawdown/VaR aggregation, and rebalancing utilities.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from src.core.logger import get_logger

logger = get_logger("portfolio")


@dataclass
class AllocationResult:
    weights: Dict[str, float]
    expected_return: float
    portfolio_vol: float
    portfolio_sharpe: float
    max_single_strategy_weight: float
    correlation_matrix: pd.DataFrame = field(default_factory=pd.DataFrame)


class PortfolioManager:
    def __init__(self, risk_free_rate: float = 0.02, rebalance_days: int = 21):
        self._risk_free_rate = risk_free_rate
        self._rebalance_days = rebalance_days
        self._strategies: Dict[str, pd.Series] = {}  # strategy_id -> NAV series

    def add_strategy(self, strategy_id: str, nav_series: pd.Series, risk_config=None) -> None:
        self._strategies[strategy_id] = nav_series

    def remove_strategy(self, strategy_id: str) -> None:
        self._strategies.pop(strategy_id, None)

    def compute_covariance(self) -> pd.DataFrame:
        """Compute annualized covariance matrix from NAV returns."""
        if len(self._strategies) < 2:
            raise ValueError("Need at least 2 strategies")
        returns = {}
        for sid, nav in self._strategies.items():
            r = nav.pct_change().dropna()
            returns[sid] = r
        df = pd.DataFrame(returns).dropna()
        return df.cov() * 252  # annualized

    def optimize_weights(
        self,
        objective: str = "sharpe",
        max_weight: float = 0.4,
        allow_short: bool = False,
        step: float = 0.05,
    ) -> AllocationResult:
        """Grid-search weight optimization."""
        if not self._strategies:
            raise ValueError("No strategies added")

        nav_map = dict(self._strategies)

        if objective == "equal_risk":
            return self._equal_risk_weights(max_weight)

        from src.optimizer.combo_optimizer import optimize_portfolio
        result = optimize_portfolio(
            nav_map=nav_map,
            step=step,
            objective=objective,
            allow_short=allow_short,
            max_weight=max_weight,
            risk_free=self._risk_free_rate,
        )

        # Compute portfolio vol from weights
        if len(self._strategies) >= 2:
            try:
                cov = self.compute_covariance()
                w = np.array([result.weights.get(k, 0) for k in sorted(cov.columns)])
                cov_vals = (
                    cov.reindex(sorted(cov.columns))
                    .reindex(sorted(cov.columns), axis=1)
                    .values
                )
                port_vol = float(np.sqrt(w @ cov_vals @ w))
            except Exception:
                port_vol = 0.0
        else:
            port_vol = 0.0

        try:
            corr = (
                self.compute_covariance().corr()
                if len(self._strategies) >= 2
                else pd.DataFrame()
            )
        except Exception:
            corr = pd.DataFrame()

        return AllocationResult(
            weights=result.weights,
            expected_return=result.stats["cagr"],
            portfolio_vol=port_vol,
            portfolio_sharpe=result.stats["sharpe"],
            max_single_strategy_weight=max(result.weights.values()) if result.weights else 0.0,
            correlation_matrix=corr,
        )

    def _equal_risk_weights(self, max_weight: float = 0.4) -> AllocationResult:
        """Inverse-volatility equal risk parity weights."""
        vols = {}
        for sid, nav in self._strategies.items():
            r = nav.pct_change().dropna()
            vols[sid] = float(r.std() * np.sqrt(252)) if len(r) > 1 else 1.0

        inv_vols = {k: 1.0 / (v if v > 0 else 1e-9) for k, v in vols.items()}
        total = sum(inv_vols.values())
        raw_weights = {k: v / total for k, v in inv_vols.items()}

        # Iterative clip-and-renormalize until all weights respect max_weight.
        # A single clip+renorm pass can push previously-below-max entries above the
        # limit, so we repeat until convergence (typically 2-4 iterations).
        weights = dict(raw_weights)
        for _ in range(100):
            clipped = {k: min(v, max_weight) for k, v in weights.items()}
            total_w = sum(clipped.values())
            if total_w <= 0:
                break
            weights = {k: v / total_w for k, v in clipped.items()}
            if all(v <= max_weight + 1e-12 for v in weights.values()):
                break

        try:
            corr = (
                self.compute_covariance().corr()
                if len(self._strategies) >= 2
                else pd.DataFrame()
            )
        except Exception:
            corr = pd.DataFrame()

        return AllocationResult(
            weights=weights,
            expected_return=0.0,
            portfolio_vol=0.0,
            portfolio_sharpe=0.0,
            max_single_strategy_weight=max(weights.values()) if weights else 0.0,
            correlation_matrix=corr,
        )

    def aggregate_risk(self, account_values: Dict[str, float]) -> dict:
        """Aggregate portfolio-level risk metrics."""
        total = sum(account_values.values())
        if total <= 0:
            return {}

        weights = {k: v / total for k, v in account_values.items()}

        # Per-strategy nav returns -> weighted portfolio return series
        all_rets = []
        for sid, nav in self._strategies.items():
            w = weights.get(sid, 0.0)
            r = nav.pct_change().dropna()
            all_rets.append(r * w)

        if not all_rets:
            return {}

        combined = pd.concat(all_rets, axis=1).sum(axis=1).dropna()
        if len(combined) == 0:
            return {}

        cumret = (1 + combined).cumprod()
        peak = cumret.cummax()
        drawdown = (peak - cumret) / peak
        max_dd = float(drawdown.max())

        # VaR and ES at 95%
        returns_arr = combined.values
        var_95 = float(np.percentile(returns_arr, 5))
        es_95 = (
            float(returns_arr[returns_arr <= var_95].mean())
            if (returns_arr <= var_95).any()
            else var_95
        )

        # Concentration (Herfindahl-Hirschman Index)
        hhi = sum(w ** 2 for w in weights.values())

        return {
            "total_value": total,
            "weights": weights,
            "max_drawdown": max_dd,
            "var_95": var_95,
            "es_95": es_95,
            "hhi_concentration": hhi,
            "num_strategies": len(account_values),
        }

    def check_rebalance_needed(
        self,
        current_weights: Dict[str, float],
        target_weights: Optional[Dict[str, float]] = None,
        threshold: float = 0.05,
    ) -> bool:
        """Return True if any weight drifted beyond threshold from target."""
        if target_weights is None:
            return False
        for sid, target in target_weights.items():
            current = current_weights.get(sid, 0.0)
            if abs(current - target) > threshold:
                return True
        return False

    def get_rebalance_orders(
        self,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float],
        account_value: float,
    ) -> List[dict]:
        """Return list of rebalance order dicts: {strategy_id, delta_value, direction}."""
        orders = []
        all_sids = set(current_weights) | set(target_weights)
        for sid in all_sids:
            cur = current_weights.get(sid, 0.0)
            tgt = target_weights.get(sid, 0.0)
            delta = (tgt - cur) * account_value
            if abs(delta) > 0.01:
                orders.append({
                    "strategy_id": sid,
                    "delta_value": round(delta, 2),
                    "direction": "increase" if delta > 0 else "decrease",
                    "current_weight": cur,
                    "target_weight": tgt,
                })
        return orders


__all__ = ["PortfolioManager", "AllocationResult"]
