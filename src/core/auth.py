"""
Simple RBAC authorization and tenant/account isolation helpers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Set


class Permission:
    ORDER_CREATE = "order.create"
    ORDER_SUBMIT = "order.submit"
    ORDER_CANCEL = "order.cancel"
    ORDER_QUERY = "order.query"
    ACCOUNT_QUERY = "account.query"
    POSITION_QUERY = "position.query"
    GATEWAY_CONNECT = "gateway.connect"
    GATEWAY_TRADE = "gateway.trade"
    ADMIN = "admin"
    # V4.0-D: Account-level permissions
    ACCOUNT_MANAGE = "account.manage"
    FUND_TRANSFER = "fund.transfer"


class Role:
    ADMIN = "admin"
    TRADER = "trader"
    VIEWER = "viewer"
    STRATEGY = "strategy"
    SYSTEM = "system"


def default_role_permissions() -> Dict[str, Set[str]]:
    return {
        Role.ADMIN: {
            Permission.ADMIN,
            Permission.ORDER_CREATE,
            Permission.ORDER_SUBMIT,
            Permission.ORDER_CANCEL,
            Permission.ORDER_QUERY,
            Permission.ACCOUNT_QUERY,
            Permission.POSITION_QUERY,
            Permission.GATEWAY_CONNECT,
            Permission.GATEWAY_TRADE,
            Permission.ACCOUNT_MANAGE,
            Permission.FUND_TRANSFER,
        },
        Role.TRADER: {
            Permission.ORDER_CREATE,
            Permission.ORDER_SUBMIT,
            Permission.ORDER_CANCEL,
            Permission.ORDER_QUERY,
            Permission.ACCOUNT_QUERY,
            Permission.POSITION_QUERY,
            Permission.GATEWAY_TRADE,
        },
        Role.STRATEGY: {
            Permission.ORDER_CREATE,
            Permission.ORDER_SUBMIT,
            Permission.ORDER_CANCEL,
            Permission.ORDER_QUERY,
        },
        Role.VIEWER: {
            Permission.ORDER_QUERY,
            Permission.ACCOUNT_QUERY,
            Permission.POSITION_QUERY,
        },
        Role.SYSTEM: {
            Permission.ADMIN,
            Permission.ORDER_CREATE,
            Permission.ORDER_SUBMIT,
            Permission.ORDER_CANCEL,
            Permission.ORDER_QUERY,
            Permission.ACCOUNT_QUERY,
            Permission.POSITION_QUERY,
            Permission.GATEWAY_CONNECT,
            Permission.GATEWAY_TRADE,
            Permission.ACCOUNT_MANAGE,
            Permission.FUND_TRANSFER,
        },
    }


@dataclass
class Subject:
    """Actor identity for authorization."""
    subject_id: str
    role: str
    tenant_id: str = ""
    strategy_id: str = ""
    account_id: str = ""

    @classmethod
    def system(cls) -> "Subject":
        return cls(subject_id="system", role=Role.SYSTEM)


@dataclass
class ResourceScope:
    """Resource scope for tenant/strategy/account isolation."""
    tenant_id: str = ""
    strategy_id: str = ""
    account_id: str = ""


class Authorizer:
    """RBAC authorizer with optional tenant/strategy/account isolation."""

    def __init__(
        self,
        role_permissions: Optional[Dict[str, Set[str]]] = None,
        *,
        enforce_tenant: bool = True,
        enforce_strategy: bool = False,
        enforce_account: bool = False,
    ) -> None:
        self._role_permissions = role_permissions or default_role_permissions()
        self.enforce_tenant = enforce_tenant
        self.enforce_strategy = enforce_strategy
        self.enforce_account = enforce_account

    def has_permission(self, permission: str, subject: Subject) -> bool:
        perms = self._role_permissions.get(subject.role, set())
        return permission in perms or Permission.ADMIN in perms

    def require(
        self,
        permission: str,
        subject: Optional[Subject],
        scope: Optional[ResourceScope] = None,
    ) -> None:
        actor = subject or Subject.system()
        if not self.has_permission(permission, actor):
            raise PermissionError(f"Permission denied: {permission} for role={actor.role}")
        self._enforce_scope(actor, scope)

    def _enforce_scope(self, actor: Subject, scope: Optional[ResourceScope]) -> None:
        if not scope:
            return
        # Admin bypasses scope checks
        if actor.role == Role.ADMIN:
            return
        if self.enforce_tenant and scope.tenant_id and actor.tenant_id:
            if scope.tenant_id != actor.tenant_id:
                raise PermissionError("Tenant isolation violation")
        if self.enforce_strategy and scope.strategy_id and actor.strategy_id:
            if scope.strategy_id != actor.strategy_id:
                raise PermissionError("Strategy isolation violation")
        if self.enforce_account and scope.account_id and actor.account_id:
            if scope.account_id != actor.account_id:
                raise PermissionError("Account isolation violation")


def normalize_permissions(perms: Iterable[str]) -> Set[str]:
    return {str(p) for p in perms}
