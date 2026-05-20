import pytest

from src.core.order_manager import OrderManager
from src.core.auth import Authorizer, Role, Subject
from src.core.interfaces import Side, OrderTypeEnum


def test_order_manager_account_group_and_strategy_isolation():
    authorizer = Authorizer()
    manager = OrderManager(
        authorizer=authorizer,
        account_group="GROUP_A",
        allowed_strategies={"s1"},
    )
    subject = Subject(subject_id="s1_user", role=Role.STRATEGY, account_group="GROUP_A", strategy_id="s1")

    order = manager.create_order(
        symbol="AAA",
        side=Side.BUY,
        quantity=10,
        price=1.0,
        order_type=OrderTypeEnum.LIMIT,
        strategy_id="s1",
        account_group="GROUP_A",
        subject=subject,
    )
    assert order.strategy_id == "s1"

    with pytest.raises(PermissionError):
        manager.create_order(
            symbol="AAA",
            side=Side.BUY,
            quantity=10,
            price=1.0,
            order_type=OrderTypeEnum.LIMIT,
            strategy_id="s2",
            account_group="GROUP_A",
            subject=subject,
        )
