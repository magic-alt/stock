from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Mapping, Optional


@dataclass(frozen=True)
class AccountCapital:
    account_id: str
    cash_balance: float
    status: str = "active"
    risk_budget: float = 1.0


@dataclass(frozen=True)
class CapitalAllocationResult:
    total_cash: float
    deployable_cash: float
    reserved_cash: float
    strategy_weights: Dict[str, float]
    account_weights: Dict[str, float]
    allocations: Dict[str, Dict[str, float]] = field(default_factory=dict)
    rejected_accounts: Dict[str, str] = field(default_factory=dict)

    def strategy_totals(self) -> Dict[str, float]:
        totals = {strategy_id: 0.0 for strategy_id in self.strategy_weights}
        for strategy_map in self.allocations.values():
            for strategy_id, amount in strategy_map.items():
                totals[strategy_id] = totals.get(strategy_id, 0.0) + amount
        return totals

    def account_totals(self) -> Dict[str, float]:
        return {account_id: sum(strategy_map.values()) for account_id, strategy_map in self.allocations.items()}


class CapitalAllocator:
    """Allocate portfolio capital across accounts and strategies."""

    def __init__(
        self,
        *,
        min_cash_buffer_pct: float = 0.05,
        max_account_weight: float = 1.0,
        max_strategy_weight: float = 0.5,
    ) -> None:
        if not 0 <= min_cash_buffer_pct < 1:
            raise ValueError("min_cash_buffer_pct must be in [0, 1)")
        if not 0 < max_account_weight <= 1:
            raise ValueError("max_account_weight must be in (0, 1]")
        if not 0 < max_strategy_weight <= 1:
            raise ValueError("max_strategy_weight must be in (0, 1]")
        self.min_cash_buffer_pct = min_cash_buffer_pct
        self.max_account_weight = max_account_weight
        self.max_strategy_weight = max_strategy_weight

    def allocate(
        self,
        accounts: Iterable[AccountCapital] | Mapping[str, float],
        strategy_weights: Mapping[str, float],
        *,
        total_capital: Optional[float] = None,
    ) -> CapitalAllocationResult:
        account_inputs = self._coerce_accounts(accounts)
        rejected = {
            account.account_id: self._rejection_reason(account)
            for account in account_inputs.values()
            if self._rejection_reason(account)
        }
        active_accounts = {
            account_id: account
            for account_id, account in account_inputs.items()
            if account_id not in rejected
        }
        if not active_accounts:
            raise ValueError("No active accounts with deployable cash")

        total_cash = sum(max(account.cash_balance, 0.0) for account in account_inputs.values())
        raw_capacities = {
            account_id: account.cash_balance * (1.0 - self.min_cash_buffer_pct) * account.risk_budget
            for account_id, account in active_accounts.items()
        }
        raw_capacities = {account_id: max(value, 0.0) for account_id, value in raw_capacities.items()}
        deployable_before_cap = sum(raw_capacities.values())
        if deployable_before_cap <= 0:
            raise ValueError("No deployable cash after buffers and risk budgets")

        account_weights = _cap_and_normalize(raw_capacities, self.max_account_weight)
        capacity_limited_cash = min(
            raw_capacities[account_id] / weight
            for account_id, weight in account_weights.items()
            if weight > 0
        )
        deployable_cash = min(deployable_before_cap, capacity_limited_cash)
        if total_capital is not None:
            deployable_cash = min(deployable_cash, max(float(total_capital), 0.0))
        if deployable_cash <= 0:
            raise ValueError("total_capital leaves no deployable cash")

        strategy_weights_normalized = _cap_and_normalize(strategy_weights, self.max_strategy_weight)
        allocations = {
            account_id: {
                strategy_id: deployable_cash * account_weight * strategy_weight
                for strategy_id, strategy_weight in strategy_weights_normalized.items()
            }
            for account_id, account_weight in account_weights.items()
        }

        return CapitalAllocationResult(
            total_cash=total_cash,
            deployable_cash=deployable_cash,
            reserved_cash=max(total_cash - deployable_cash, 0.0),
            strategy_weights=strategy_weights_normalized,
            account_weights=account_weights,
            allocations=allocations,
            rejected_accounts=rejected,
        )

    @staticmethod
    def _coerce_accounts(accounts: Iterable[AccountCapital] | Mapping[str, float]) -> Dict[str, AccountCapital]:
        if isinstance(accounts, Mapping):
            return {
                str(account_id): AccountCapital(str(account_id), float(cash))
                for account_id, cash in accounts.items()
            }
        result: Dict[str, AccountCapital] = {}
        for account in accounts:
            if isinstance(account, AccountCapital):
                result[account.account_id] = account
                continue
            account_id = str(getattr(account, "account_id"))
            cash_balance = float(getattr(account, "cash_balance", getattr(account, "cash", 0.0)))
            status = str(getattr(account, "status", "active"))
            risk_budget = float(getattr(account, "risk_budget", getattr(account, "metadata", {}).get("risk_budget", 1.0)))
            result[account_id] = AccountCapital(account_id, cash_balance, status=status, risk_budget=risk_budget)
        return result

    @staticmethod
    def _rejection_reason(account: AccountCapital) -> str:
        if account.status != "active":
            return f"account status is {account.status}"
        if account.cash_balance <= 0:
            return "cash balance is not positive"
        if account.risk_budget <= 0:
            return "risk budget is not positive"
        return ""


def _normalize(values: Mapping[str, float]) -> Dict[str, float]:
    positive = {key: max(float(value), 0.0) for key, value in values.items() if float(value) > 0}
    total = sum(positive.values())
    if total <= 0:
        raise ValueError("weights must contain positive values")
    return {key: value / total for key, value in positive.items()}


def _cap_and_normalize(values: Mapping[str, float], max_weight: float) -> Dict[str, float]:
    weights = _normalize(values)
    if len(weights) == 1:
        key = next(iter(weights))
        return {key: 1.0}
    if max_weight * len(weights) < 1.0 - 1e-12:
        raise ValueError("max_strategy_weight is too small for the number of strategies")

    capped: Dict[str, float] = {}
    uncapped = dict(weights)
    remaining_weight = 1.0
    for _ in range(len(weights)):
        if not uncapped:
            break
        normalized = _normalize(uncapped)
        breached = {key: weight for key, weight in normalized.items() if weight * remaining_weight > max_weight}
        if not breached:
            for key, weight in normalized.items():
                capped[key] = weight * remaining_weight
            break
        for key in breached:
            capped[key] = max_weight
            remaining_weight -= max_weight
            uncapped.pop(key, None)

    total = sum(capped.values())
    if total <= 0:
        raise ValueError("strategy weights cannot be normalized")
    return {key: value / total for key, value in capped.items()}


__all__ = ["AccountCapital", "CapitalAllocationResult", "CapitalAllocator"]
