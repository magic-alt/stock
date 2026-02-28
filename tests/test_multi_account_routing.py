"""
Tests for multi-account routing and AccountManager.
"""
import pytest

from src.core.auth import Authorizer, Permission, ResourceScope, Role, Subject
from src.core.account_manager import AccountManager, AccountInfo


class TestAccountManager:
    def test_create_account(self):
        mgr = AccountManager()
        acc = mgr.create_account("T1", "owner1", 1000.0)
        assert acc.tenant_id == "T1"
        assert acc.owner_subject_id == "owner1"
        assert acc.cash_balance == 1000.0
        assert acc.status == "active"

    def test_get_account(self):
        mgr = AccountManager()
        acc = mgr.create_account("T1", "owner1", 500.0)
        fetched = mgr.get_account(acc.account_id)
        assert fetched.account_id == acc.account_id

    def test_get_account_not_found(self):
        mgr = AccountManager()
        with pytest.raises(KeyError):
            mgr.get_account("nonexistent")

    def test_list_accounts_by_tenant(self):
        mgr = AccountManager()
        mgr.create_account("T1", "o1", 100.0)
        mgr.create_account("T1", "o2", 200.0)
        mgr.create_account("T2", "o3", 300.0)
        t1_accounts = mgr.list_accounts("T1")
        assert len(t1_accounts) == 2
        assert all(a.tenant_id == "T1" for a in t1_accounts)

    def test_fund_transfer_success(self):
        mgr = AccountManager()
        a1 = mgr.create_account("T1", "o1", 1000.0)
        a2 = mgr.create_account("T1", "o2", 500.0)
        result = mgr.fund_transfer(a1.account_id, a2.account_id, 300.0)
        assert result["from_balance"] == 700.0
        assert result["to_balance"] == 800.0

    def test_fund_transfer_insufficient_balance(self):
        mgr = AccountManager()
        a1 = mgr.create_account("T1", "o1", 100.0)
        a2 = mgr.create_account("T1", "o2", 0.0)
        with pytest.raises(ValueError, match="Insufficient"):
            mgr.fund_transfer(a1.account_id, a2.account_id, 500.0)

    def test_fund_transfer_unauthorized(self):
        auth = Authorizer(enforce_account=True)
        mgr = AccountManager(authorizer=auth)
        viewer = Subject(subject_id="v1", role=Role.VIEWER, tenant_id="T1", account_id="acc1")
        a1 = mgr.create_account("T1", "o1", 1000.0)
        a2 = mgr.create_account("T1", "o2", 0.0)
        with pytest.raises(PermissionError):
            mgr.fund_transfer(a1.account_id, a2.account_id, 100.0, subject=viewer)

    def test_close_account(self):
        mgr = AccountManager()
        acc = mgr.create_account("T1", "o1", 0.0)
        closed = mgr.close_account(acc.account_id)
        assert closed.status == "closed"

    def test_account_risk_summary(self):
        mgr = AccountManager()
        acc = mgr.create_account("T1", "o1", 5000.0)
        summary = mgr.get_account_risk_summary(acc.account_id)
        assert summary["account_id"] == acc.account_id
        assert summary["risk_level"] == "low"

    def test_transfer_closed_account_rejected(self):
        mgr = AccountManager()
        a1 = mgr.create_account("T1", "o1", 1000.0)
        a2 = mgr.create_account("T1", "o2", 0.0)
        mgr.close_account(a2.account_id)
        with pytest.raises(ValueError, match="active"):
            mgr.fund_transfer(a1.account_id, a2.account_id, 100.0)


class TestMultiAccountRBAC:
    def test_account_isolation(self):
        auth = Authorizer(enforce_account=True)
        trader = Subject(subject_id="t1", role=Role.TRADER, tenant_id="T1", account_id="A1")
        with pytest.raises(PermissionError, match="Account isolation"):
            auth.require(
                Permission.ORDER_QUERY,
                trader,
                ResourceScope(tenant_id="T1", account_id="A2"),
            )

    def test_admin_bypasses_account_isolation(self):
        auth = Authorizer(enforce_account=True)
        admin = Subject(subject_id="a1", role=Role.ADMIN, tenant_id="T1", account_id="A1")
        auth.require(
            Permission.ORDER_QUERY,
            admin,
            ResourceScope(tenant_id="T1", account_id="A2"),
        )

    def test_account_manage_permission(self):
        auth = Authorizer()
        admin = Subject(subject_id="a1", role=Role.ADMIN, tenant_id="T1")
        assert auth.has_permission(Permission.ACCOUNT_MANAGE, admin)

    def test_fund_transfer_permission(self):
        auth = Authorizer()
        admin = Subject(subject_id="a1", role=Role.ADMIN, tenant_id="T1")
        assert auth.has_permission(Permission.FUND_TRANSFER, admin)

        viewer = Subject(subject_id="v1", role=Role.VIEWER, tenant_id="T1")
        assert not auth.has_permission(Permission.FUND_TRANSFER, viewer)


class TestMultiAccountRouting:
    def test_order_routed_to_correct_account(self):
        auth = Authorizer(enforce_account=True)
        mgr = AccountManager(authorizer=auth)
        admin = Subject(subject_id="admin", role=Role.ADMIN, tenant_id="T1")
        acc = mgr.create_account("T1", "admin", 10000.0, subject=admin)
        fetched = mgr.get_account(acc.account_id)
        assert fetched.tenant_id == "T1"

    def test_cross_account_order_rejected(self):
        auth = Authorizer(enforce_account=True)
        trader = Subject(subject_id="t1", role=Role.TRADER, tenant_id="T1", account_id="A1")
        with pytest.raises(PermissionError):
            auth.require(
                Permission.ORDER_SUBMIT,
                trader,
                ResourceScope(tenant_id="T1", account_id="A2"),
            )

    def test_tenant_scoped_account_list(self):
        mgr = AccountManager()
        mgr.create_account("T1", "o1")
        mgr.create_account("T2", "o2")
        assert len(mgr.list_accounts("T1")) == 1
        assert len(mgr.list_accounts("T2")) == 1
        assert len(mgr.list_accounts("T3")) == 0
