"""
Multi-account management with tenant isolation and fund transfer.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.core.auth import (
    Authorizer,
    Permission,
    ResourceScope,
    Subject,
)


@dataclass
class AccountInfo:
    """Account state."""
    account_id: str
    tenant_id: str
    owner_subject_id: str
    cash_balance: float
    status: str = "active"  # active, frozen, closed
    metadata: Dict[str, Any] = field(default_factory=dict)


class AccountManager:
    """Manages multiple accounts with tenant isolation and authorization."""

    def __init__(self, authorizer: Optional[Authorizer] = None) -> None:
        self._authorizer = authorizer
        self._accounts: Dict[str, AccountInfo] = {}

    def create_account(
        self,
        tenant_id: str,
        owner_id: str,
        initial_cash: float = 0.0,
        *,
        subject: Optional[Subject] = None,
    ) -> AccountInfo:
        if self._authorizer and subject:
            self._authorizer.require(
                Permission.ACCOUNT_MANAGE,
                subject,
                ResourceScope(tenant_id=tenant_id),
            )
        account_id = str(uuid.uuid4())[:8]
        account = AccountInfo(
            account_id=account_id,
            tenant_id=tenant_id,
            owner_subject_id=owner_id,
            cash_balance=initial_cash,
        )
        self._accounts[account_id] = account
        return account

    def get_account(self, account_id: str) -> AccountInfo:
        if account_id not in self._accounts:
            raise KeyError(f"Account not found: {account_id}")
        return self._accounts[account_id]

    def list_accounts(self, tenant_id: str) -> List[AccountInfo]:
        return [a for a in self._accounts.values() if a.tenant_id == tenant_id]

    def fund_transfer(
        self,
        from_account_id: str,
        to_account_id: str,
        amount: float,
        *,
        subject: Optional[Subject] = None,
    ) -> Dict[str, Any]:
        if amount <= 0:
            raise ValueError("Transfer amount must be positive")

        from_acc = self.get_account(from_account_id)
        to_acc = self.get_account(to_account_id)

        if self._authorizer and subject:
            self._authorizer.require(
                Permission.FUND_TRANSFER,
                subject,
                ResourceScope(tenant_id=from_acc.tenant_id, account_id=from_account_id),
            )

        if from_acc.status != "active" or to_acc.status != "active":
            raise ValueError("Both accounts must be active for transfer")

        if from_acc.cash_balance < amount:
            raise ValueError(
                f"Insufficient balance: {from_acc.cash_balance:.2f} < {amount:.2f}"
            )

        from_acc.cash_balance -= amount
        to_acc.cash_balance += amount

        return {
            "from_account": from_account_id,
            "to_account": to_account_id,
            "amount": amount,
            "from_balance": from_acc.cash_balance,
            "to_balance": to_acc.cash_balance,
        }

    def close_account(
        self,
        account_id: str,
        *,
        subject: Optional[Subject] = None,
    ) -> AccountInfo:
        account = self.get_account(account_id)

        if self._authorizer and subject:
            self._authorizer.require(
                Permission.ACCOUNT_MANAGE,
                subject,
                ResourceScope(tenant_id=account.tenant_id, account_id=account_id),
            )

        account.status = "closed"
        return account

    def get_account_risk_summary(self, account_id: str) -> Dict[str, Any]:
        account = self.get_account(account_id)
        return {
            "account_id": account.account_id,
            "tenant_id": account.tenant_id,
            "cash_balance": account.cash_balance,
            "status": account.status,
            "risk_level": "low" if account.cash_balance > 0 else "high",
        }
