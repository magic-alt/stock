from __future__ import annotations

import pytest

from src.core.account_manager import AccountInfo
from src.core.capital_allocator import AccountCapital, CapitalAllocator


def test_allocator_builds_account_strategy_matrix():
    allocator = CapitalAllocator(min_cash_buffer_pct=0.1, max_account_weight=0.7, max_strategy_weight=0.7)
    result = allocator.allocate(
        {"acct_a": 100_000.0, "acct_b": 50_000.0},
        {"s1": 0.6, "s2": 0.4},
    )

    assert result.deployable_cash == pytest.approx(135_000.0)
    assert result.reserved_cash == pytest.approx(15_000.0)
    assert set(result.allocations) == {"acct_a", "acct_b"}
    assert result.strategy_totals()["s1"] == pytest.approx(result.deployable_cash * 0.6)
    assert result.strategy_totals()["s2"] == pytest.approx(result.deployable_cash * 0.4)


def test_allocator_respects_max_account_weight():
    allocator = CapitalAllocator(min_cash_buffer_pct=0.0, max_account_weight=0.6, max_strategy_weight=1.0)
    result = allocator.allocate({"large": 900.0, "small": 100.0}, {"s1": 1.0})

    assert result.account_totals()["large"] <= result.deployable_cash * 0.6 + 1e-9
    assert result.account_totals()["small"] == pytest.approx(100.0)


def test_allocator_caps_and_redistributes_strategy_weights():
    allocator = CapitalAllocator(min_cash_buffer_pct=0.0, max_strategy_weight=0.6)
    result = allocator.allocate({"acct": 1000.0}, {"s1": 0.9, "s2": 0.1})

    assert result.strategy_weights["s1"] == pytest.approx(0.6)
    assert result.strategy_weights["s2"] == pytest.approx(0.4)
    assert result.strategy_totals()["s1"] == pytest.approx(600.0)


def test_allocator_rejects_inactive_or_empty_accounts():
    allocator = CapitalAllocator(min_cash_buffer_pct=0.0)
    result = allocator.allocate(
        [
            AccountCapital("active", 100.0),
            AccountCapital("closed", 100.0, status="closed"),
            AccountCapital("empty", 0.0),
        ],
        {"s1": 1.0},
    )

    assert result.deployable_cash == pytest.approx(100.0)
    assert result.rejected_accounts["closed"] == "account status is closed"
    assert result.rejected_accounts["empty"] == "cash balance is not positive"


def test_allocator_accepts_account_manager_accounts():
    allocator = CapitalAllocator(min_cash_buffer_pct=0.0, max_strategy_weight=1.0)
    accounts = [
        AccountInfo(account_id="acct_a", tenant_id="t1", owner_subject_id="u1", cash_balance=100.0),
        AccountInfo(account_id="acct_b", tenant_id="t1", owner_subject_id="u2", cash_balance=300.0),
    ]

    result = allocator.allocate(accounts, {"s1": 1.0}, total_capital=200.0)

    assert result.deployable_cash == pytest.approx(200.0)
    assert result.total_cash == pytest.approx(400.0)
    assert result.account_totals()["acct_b"] > result.account_totals()["acct_a"]


def test_allocator_raises_when_no_account_can_deploy():
    allocator = CapitalAllocator()
    with pytest.raises(ValueError, match="No active accounts"):
        allocator.allocate([AccountCapital("closed", 100.0, status="closed")], {"s1": 1.0})


def test_allocator_raises_when_strategy_cap_is_infeasible():
    allocator = CapitalAllocator(max_strategy_weight=0.4)
    with pytest.raises(ValueError, match="too small"):
        allocator.allocate({"acct": 100.0}, {"s1": 0.5, "s2": 0.5})
