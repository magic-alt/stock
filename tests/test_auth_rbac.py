
from __future__ import annotations

import pytest

from src.core.auth import Authorizer, Permission, ResourceScope, Role, Subject

def test_rbac_denies_viewer_submit():
    auth = Authorizer()
    viewer = Subject(subject_id="v1", role=Role.VIEWER, account_group="G1")
    with pytest.raises(PermissionError):
        auth.require(Permission.ORDER_SUBMIT, viewer, ResourceScope(account_group="G1"))

def test_account_group_isolation():
    auth = Authorizer(enforce_account_group=True)
    trader = Subject(subject_id="t1", role=Role.TRADER, account_group="GROUP_A")
    with pytest.raises(PermissionError):
        auth.require(Permission.ORDER_QUERY, trader, ResourceScope(account_group="GROUP_B"))

# ---------------------------------------------------------------------------
# Account isolation tests (V4.0-D)
# ---------------------------------------------------------------------------

def test_account_isolation():
    auth = Authorizer(enforce_account=True)
    trader = Subject(subject_id="t1", role=Role.TRADER, account_group="G1", account_id="A1")
    with pytest.raises(PermissionError, match="Account isolation"):
        auth.require(Permission.ORDER_QUERY, trader, ResourceScope(account_group="G1", account_id="A2"))

def test_admin_bypasses_account_isolation():
    auth = Authorizer(enforce_account=True)
    admin = Subject(subject_id="a1", role=Role.ADMIN, account_group="G1", account_id="A1")
    # Should not raise
    auth.require(Permission.ORDER_QUERY, admin, ResourceScope(account_group="G1", account_id="A2"))

def test_account_manage_permission():
    auth = Authorizer()
    admin = Subject(subject_id="a1", role=Role.ADMIN, account_group="G1")
    assert auth.has_permission(Permission.ACCOUNT_MANAGE, admin)

    viewer = Subject(subject_id="v1", role=Role.VIEWER, account_group="G1")
    assert not auth.has_permission(Permission.ACCOUNT_MANAGE, viewer)

def test_fund_transfer_permission():
    auth = Authorizer()
    admin = Subject(subject_id="a1", role=Role.ADMIN, account_group="G1")
    assert auth.has_permission(Permission.FUND_TRANSFER, admin)

    trader = Subject(subject_id="t1", role=Role.TRADER, account_group="G1")
    assert not auth.has_permission(Permission.FUND_TRANSFER, trader)
