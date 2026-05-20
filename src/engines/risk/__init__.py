"""Risk engine — V6 ring wrapper over V5 risk primitives.

Re-exports the per-account :class:`RiskManagerV2`, pre-trade decision
types and the reconciliation runner that compares backtest vs paper /
live state.  Satisfies the V6 ``RiskCheckerPort`` /
``RiskMonitorPort`` ports declared in
:mod:`src.core.contracts.ports.risk`.

Note: the V5 risk module exposes a class also named ``RiskCheckResult``;
it is unrelated to the V6 contract DTO of the same name in
:mod:`src.core.contracts.dto` and is re-exported under the V5-specific
name ``RiskCheckOutcome`` to avoid shadowing the SSOT type.
"""

from __future__ import annotations

from src.core.pre_trade_risk import RiskDecision as PreTradeRiskDecision
from src.core.reconciliation import ReconciliationReport, Reconciler
from src.core.risk_manager_v2 import (
    DailyRiskStats,
    PositionStop,
    RiskCheckResult as RiskCheckOutcome,
    RiskConfig,
    RiskEventType,
    RiskLevel,
    RiskManagerV2,
)

__all__ = (
    "RiskManagerV2",
    "RiskConfig",
    "RiskEventType",
    "RiskLevel",
    "PositionStop",
    "DailyRiskStats",
    "RiskCheckOutcome",
    "PreTradeRiskDecision",
    "Reconciler",
    "ReconciliationReport",
)
