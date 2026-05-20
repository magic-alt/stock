"""Risk-plane ports: pre-trade rules and admission gates."""
from __future__ import annotations

from typing import Protocol, Sequence, runtime_checkable

from ..dto import AccountSnapshot, Order, RiskCheckResult, Signal


@runtime_checkable
class RiskRulePort(Protocol):
    """A single composable risk rule.

    Rules MUST be pure functions of their inputs. The engine composes
    multiple rules and stops at the first non-approved decision.
    """

    @property
    def rule_id(self) -> str:
        """Stable identifier surfaced in :class:`RiskCheckResult.rule_id`."""

    def check_signal(
        self,
        signal: Signal,
        *,
        account: AccountSnapshot,
    ) -> RiskCheckResult:
        ...

    def check_order(
        self,
        order: Order,
        *,
        account: AccountSnapshot,
    ) -> RiskCheckResult:
        ...


@runtime_checkable
class AdmissionGatePort(Protocol):
    """Strategy admission workflow (V5 ``StrategyAdmissionWorkflow``).

    Decides whether a candidate strategy may transition between lifecycle
    stages (e.g. ``research → paper → live``). Implementations typically
    require artefacts: backtest report, oos report, factor stability.
    """

    def required_artifacts(self, target_stage: str) -> Sequence[str]:
        ...

    def evaluate(
        self,
        strategy_id: str,
        target_stage: str,
        artifacts: dict,
    ) -> RiskCheckResult:
        ...


__all__ = ["AdmissionGatePort", "RiskRulePort"]
