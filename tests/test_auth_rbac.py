import pytest

from src.core.auth import Authorizer, Permission, ResourceScope, Role, Subject


def test_rbac_denies_viewer_submit():
    auth = Authorizer()
    viewer = Subject(subject_id="v1", role=Role.VIEWER, tenant_id="T1")
    with pytest.raises(PermissionError):
        auth.require(Permission.ORDER_SUBMIT, viewer, ResourceScope(tenant_id="T1"))


def test_tenant_isolation():
    auth = Authorizer(enforce_tenant=True)
    trader = Subject(subject_id="t1", role=Role.TRADER, tenant_id="TENANT_A")
    with pytest.raises(PermissionError):
        auth.require(Permission.ORDER_QUERY, trader, ResourceScope(tenant_id="TENANT_B"))


# ---------------------------------------------------------------------------
# Account isolation tests (V4.0-D)
# ---------------------------------------------------------------------------


def test_account_isolation():
    auth = Authorizer(enforce_account=True)
    trader = Subject(subject_id="t1", role=Role.TRADER, tenant_id="T1", account_id="A1")
    with pytest.raises(PermissionError, match="Account isolation"):
        auth.require(Permission.ORDER_QUERY, trader, ResourceScope(tenant_id="T1", account_id="A2"))


def test_admin_bypasses_account_isolation():
    auth = Authorizer(enforce_account=True)
    admin = Subject(subject_id="a1", role=Role.ADMIN, tenant_id="T1", account_id="A1")
    # Should not raise
    auth.require(Permission.ORDER_QUERY, admin, ResourceScope(tenant_id="T1", account_id="A2"))


def test_account_manage_permission():
    auth = Authorizer()
    admin = Subject(subject_id="a1", role=Role.ADMIN, tenant_id="T1")
    assert auth.has_permission(Permission.ACCOUNT_MANAGE, admin)

    viewer = Subject(subject_id="v1", role=Role.VIEWER, tenant_id="T1")
    assert not auth.has_permission(Permission.ACCOUNT_MANAGE, viewer)


def test_fund_transfer_permission():
    auth = Authorizer()
    admin = Subject(subject_id="a1", role=Role.ADMIN, tenant_id="T1")
    assert auth.has_permission(Permission.FUND_TRANSFER, admin)

    trader = Subject(subject_id="t1", role=Role.TRADER, tenant_id="T1")
    assert not auth.has_permission(Permission.FUND_TRANSFER, trader)
