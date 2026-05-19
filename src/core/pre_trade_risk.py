"""Shared pre-trade risk evaluation helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from src.core.interfaces import AccountInfo, OrderRequest, PositionInfo


@dataclass(frozen=True)
class RiskDecision:
    """Stable decision payload returned by all pre-trade risk paths."""

    passed: bool
    rule_name: str = "all_checks"
    reason: str = "OK"
    raw_result: Optional[Any] = None

    def __bool__(self) -> bool:
        return self.passed


def evaluate_pre_trade_risk(
    risk_manager: Any,
    request: OrderRequest,
    *,
    account: AccountInfo,
    positions: Dict[str, PositionInfo],
    price: float,
) -> RiskDecision:
    """Evaluate one order with a RiskManagerV2-compatible object."""
    if risk_manager is None:
        return RiskDecision(passed=True, reason="risk manager not configured")

    result = risk_manager.check_order(
        symbol=request.symbol,
        side=request.side,
        quantity=request.quantity,
        price=price,
        account=account,
        positions=positions,
    )
    return RiskDecision(
        passed=bool(result),
        rule_name=str(getattr(result, "rule_name", "unknown")),
        reason=str(getattr(result, "reason", "")),
        raw_result=result,
    )