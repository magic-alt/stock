"""
Rebalance Executor

Bridges :class:`~src.core.portfolio.PortfolioManager` rebalance output to
:class:`~src.core.order_manager.OrderManager` order input.

The :class:`RebalanceExecutor` translates target portfolio weights into
concrete buy/sell orders, respecting minimum trade sizes and rounding to
lot sizes where applicable.

Usage::

    from src.core.rebalance_executor import RebalanceExecutor

    executor = RebalanceExecutor(portfolio_manager, order_manager)
    order_ids = executor.execute_rebalance(
        target_weights={"600519.SH": 0.3, "000001.SZ": 0.7},
        current_positions={"600519.SH": 50},
        prices={"600519.SH": 1800.0, "000001.SZ": 12.5},
        total_value=200_000.0,
    )
    print(f"Created {len(order_ids)} orders")

Integration points:
    - Call from :mod:`src.core.paper_runner_v3` or :mod:`src.core.live_runner`
      after portfolio optimisation.
    - Handles both buy and sell orders.
    - Respects minimum trade sizes and lot rounding.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from src.core.interfaces import Side, OrderTypeEnum

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class RebalanceConfig:
    """Configuration knobs for the rebalance executor.

    Attributes:
        min_trade_value: Minimum order value in currency units. Orders
            below this threshold are skipped to avoid dust trades.
        lot_size: Round order quantities down to the nearest multiple
            of ``lot_size`` (e.g. 100 for CN A-shares). Set to 1 to
            disable rounding.
        order_type: Default order type for rebalance orders.
        strategy_id: Optional strategy tag attached to every order.
        account_group: Optional account-group tag for isolation.
        max_slippage_pct: Maximum expected slippage (informational,
            not enforced — logged as a warning when exceeded).
    """
    min_trade_value: float = 500.0
    lot_size: int = 100
    order_type: OrderTypeEnum = OrderTypeEnum.LIMIT
    strategy_id: str = "rebalance"
    account_group: str = ""
    max_slippage_pct: float = 0.005


# ---------------------------------------------------------------------------
# Rebalance Executor
# ---------------------------------------------------------------------------

class RebalanceExecutor:
    """Translate portfolio target weights into concrete orders.

    This class does **not** own a portfolio manager or order manager
    reference — it accepts them at construction time so that callers
    retain full control over their lifecycle.

    Args:
        order_manager: An :class:`~src.core.order_manager.OrderManager`
            (or any object with a ``create_order`` method).
        portfolio_manager: An optional
            :class:`~src.core.portfolio.PortfolioManager`.  When provided,
            :meth:`execute_from_portfolio` can use
            ``get_rebalance_orders()`` directly.
        config: Optional :class:`RebalanceConfig`.
    """

    def __init__(
        self,
        order_manager: Any,
        portfolio_manager: Any = None,
        config: Optional[RebalanceConfig] = None,
    ) -> None:
        self._order_manager = order_manager
        self._portfolio_manager = portfolio_manager
        self._config = config or RebalanceConfig()

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def execute_rebalance(
        self,
        target_weights: Dict[str, float],
        current_positions: Dict[str, float],
        prices: Dict[str, float],
        total_value: float,
        *,
        order_type: Optional[OrderTypeEnum] = None,
        strategy_id: Optional[str] = None,
        account_group: Optional[str] = None,
    ) -> List[str]:
        """Compute required trades and create orders via the OrderManager.

        Args:
            target_weights: Desired portfolio weights per symbol
                (e.g. ``{"600519.SH": 0.3, "000001.SZ": 0.7}``).
            current_positions: Current position size per symbol
                (number of shares, not value).
            prices: Current market price per symbol.
            total_value: Total portfolio value (cash + positions).
            order_type: Override default order type.
            strategy_id: Override default strategy tag.
            account_group: Override default account group.

        Returns:
            List of created order IDs. Empty list if no trades needed.
        """
        cfg = self._config
        otype = order_type or cfg.order_type
        sid = strategy_id or cfg.strategy_id
        ag = account_group or cfg.account_group

        order_ids: List[str] = []
        all_symbols: Set[str] = set(target_weights) | set(current_positions)

        for symbol in sorted(all_symbols):
            target_w = target_weights.get(symbol, 0.0)
            price = prices.get(symbol)

            if price is None or price <= 0:
                logger.warning(
                    "rebalance: skipping %s — no valid price", symbol
                )
                continue

            current_shares = current_positions.get(symbol, 0.0)
            current_value = current_shares * price
            target_value = total_value * target_w
            delta_value = target_value - current_value

            # Skip dust trades
            if abs(delta_value) < cfg.min_trade_value:
                continue

            # Compute target shares
            target_shares = target_value / price
            delta_shares = target_shares - current_shares

            if abs(delta_shares) < 1:
                continue

            # Determine side and quantity
            if delta_shares > 0:
                side = Side.BUY
                quantity = self._round_lot(delta_shares, cfg.lot_size)
            else:
                side = Side.SELL
                quantity = self._round_lot(abs(delta_shares), cfg.lot_size)

            if quantity <= 0:
                continue

            # Final value check after rounding
            trade_value = quantity * price
            if trade_value < cfg.min_trade_value:
                continue

            try:
                order = self._order_manager.create_order(
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    price=price,
                    order_type=otype,
                    strategy_id=sid,
                    account_group=ag,
                    tags={"source": "rebalance"},
                )
                order_ids.append(order.order_id)
                logger.info(
                    "rebalance: %s %s %d @ %.2f (delta_value=%.2f)",
                    side.value, symbol, quantity, price, delta_value,
                )
            except Exception as exc:
                logger.error(
                    "rebalance: order creation failed for %s — %s",
                    symbol, exc,
                )

        logger.info(
            "rebalance complete: %d orders created", len(order_ids)
        )
        return order_ids

    # ------------------------------------------------------------------
    # PortfolioManager integration
    # ------------------------------------------------------------------

    def execute_from_portfolio(
        self,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float],
        prices: Dict[str, float],
        total_value: float,
        current_positions: Optional[Dict[str, float]] = None,
    ) -> List[str]:
        """Execute rebalance using :class:`PortfolioManager.get_rebalance_orders`.

        This delegates the weight-delta computation to
        :meth:`PortfolioManager.get_rebalance_orders` (when available)
        and then converts the strategy-level deltas into symbol-level
        orders.

        Args:
            current_weights: Current weight per symbol.
            target_weights: Target weight per symbol.
            prices: Current prices.
            total_value: Total portfolio value.
            current_positions: Current shares per symbol.  If ``None``,
                they are inferred from ``current_weights`` and prices.

        Returns:
            List of created order IDs.
        """
        if current_positions is None:
            current_positions = {}
            for sym, w in current_weights.items():
                p = prices.get(sym, 0.0)
                if p > 0:
                    current_positions[sym] = (w * total_value) / p

        return self.execute_rebalance(
            target_weights=target_weights,
            current_positions=current_positions,
            prices=prices,
            total_value=total_value,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _round_lot(shares: float, lot_size: int) -> int:
        """Round shares down to the nearest lot size.

        >>> RebalanceExecutor._round_lot(247.8, 100)
        200
        >>> RebalanceExecutor._round_lot(50.0, 1)
        50
        """
        if lot_size <= 1:
            return int(shares)
        return int(shares // lot_size) * lot_size

    def preview(
        self,
        target_weights: Dict[str, float],
        current_positions: Dict[str, float],
        prices: Dict[str, float],
        total_value: float,
    ) -> List[Dict[str, Any]]:
        """Dry-run preview: return the planned trades without creating orders.

        Returns a list of dicts with keys ``symbol``, ``side``, ``quantity``,
        ``price``, ``value``, and ``delta_value``.
        """
        cfg = self._config
        plan: List[Dict[str, Any]] = []
        all_symbols: Set[str] = set(target_weights) | set(current_positions)

        for symbol in sorted(all_symbols):
            target_w = target_weights.get(symbol, 0.0)
            price = prices.get(symbol)
            if price is None or price <= 0:
                continue

            current_shares = current_positions.get(symbol, 0.0)
            current_value = current_shares * price
            target_value = total_value * target_w
            delta_value = target_value - current_value

            if abs(delta_value) < cfg.min_trade_value:
                continue

            target_shares = target_value / price
            delta_shares = target_shares - current_shares
            if abs(delta_shares) < 1:
                continue

            side = Side.BUY if delta_shares > 0 else Side.SELL
            quantity = self._round_lot(abs(delta_shares), cfg.lot_size)
            if quantity <= 0:
                continue

            plan.append({
                "symbol": symbol,
                "side": side.value,
                "quantity": quantity,
                "price": price,
                "value": quantity * price,
                "delta_value": round(delta_value, 2),
            })

        return plan


__all__ = [
    "RebalanceConfig",
    "RebalanceExecutor",
]
