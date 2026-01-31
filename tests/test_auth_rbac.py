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
