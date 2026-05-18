"""Tests for OrderStateMachine and BaseLiveGateway._safe_call helpers.

These tests cover the V3.3.0 additions to ``src.gateways.base_live_gateway``:

- Legal vs illegal transitions through :class:`OrderStateMachine`.
- Audit history capture and querying.
- ``BaseLiveGateway._transition_order`` integration (strict vs lenient mode).
- ``BaseLiveGateway._safe_call`` retry, degrade-on-missing-SDK, and on_error
  fallback semantics.
"""
from __future__ import annotations

from queue import Queue

import pytest

from src.gateways.base_live_gateway import (
    BaseLiveGateway,
    GatewayConfig,
    GatewayUnavailable,
    InvalidOrderStateTransition,
    OrderRequest,
    OrderStateMachine,
    OrderStatus,
    OrderUpdate,
)


# ---------------------------------------------------------------------------
# OrderStateMachine
# ---------------------------------------------------------------------------


def test_state_machine_legal_lifecycle():
    sm = OrderStateMachine()
    sm.register("o1", OrderStatus.PENDING_SUBMIT)
    sm.transition("o1", OrderStatus.SUBMITTED, reason="ack")
    sm.transition("o1", OrderStatus.PARTIALLY_FILLED, reason="fill1")
    sm.transition("o1", OrderStatus.PARTIALLY_FILLED, reason="fill2")
    sm.transition("o1", OrderStatus.FILLED, reason="done")
    assert sm.current("o1") == OrderStatus.FILLED
    assert sm.is_terminal("o1")
    history = sm.history("o1")
    # PENDING->SUBMITTED, SUBMITTED->PARTIAL, PARTIAL->PARTIAL, PARTIAL->FILLED
    assert [t.to_state for t in history] == [
        OrderStatus.SUBMITTED,
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED,
    ]


def test_state_machine_illegal_transition_strict_raises():
    sm = OrderStateMachine()
    sm.register("o1", OrderStatus.PENDING_SUBMIT)
    sm.transition("o1", OrderStatus.SUBMITTED)
    sm.transition("o1", OrderStatus.FILLED)
    # Terminal state -> any other state must raise.
    with pytest.raises(InvalidOrderStateTransition):
        sm.transition("o1", OrderStatus.SUBMITTED, strict=True)


def test_state_machine_illegal_transition_lenient_records_rejected():
    sm = OrderStateMachine()
    sm.register("o1", OrderStatus.PENDING_SUBMIT)
    sm.transition("o1", OrderStatus.FILLED, strict=False)  # illegal, rejected
    history = sm.history("o1")
    assert history[-1].to_state == OrderStatus.FILLED
    assert "[rejected]" in history[-1].reason
    # Lenient mode records the attempt but must NOT mutate current state.
    assert sm.current("o1") == OrderStatus.PENDING_SUBMIT


def test_state_machine_cancel_pending_then_cancelled():
    sm = OrderStateMachine()
    sm.register("o1")
    sm.transition("o1", OrderStatus.SUBMITTED)
    sm.transition("o1", OrderStatus.CANCEL_PENDING)
    sm.transition("o1", OrderStatus.CANCELLED)
    assert sm.is_terminal("o1")


def test_state_machine_history_global_and_filtered():
    sm = OrderStateMachine()
    sm.register("a")
    sm.register("b")
    sm.transition("a", OrderStatus.SUBMITTED)
    sm.transition("b", OrderStatus.SUBMITTED)
    sm.transition("b", OrderStatus.REJECTED)
    assert len(sm.history()) == 3
    assert len(sm.history("a")) == 1
    assert len(sm.history("b")) == 2


def test_state_machine_history_bounded():
    sm = OrderStateMachine(history_limit=20)
    for i in range(60):
        oid = f"o{i}"
        sm.register(oid)
        sm.transition(oid, OrderStatus.SUBMITTED)
    # History pruning drops in batches of (limit // 10) when overflowing.
    assert len(sm.history()) <= 20 + 2


# ---------------------------------------------------------------------------
# BaseLiveGateway integration (using a minimal concrete subclass)
# ---------------------------------------------------------------------------


class _DummyGateway(BaseLiveGateway):
    """Minimal concrete gateway for unit-testing base-class hooks."""

    def __init__(self, *, stub_mode: bool = False):
        config = GatewayConfig(account_id="TEST", broker="dummy")
        super().__init__(config, Queue())
        self._stub_mode = stub_mode
        self._connected = True  # allow send_order without real connect
        # Override status without going through connect()
        from src.gateways.base_live_gateway import GatewayStatus
        self._status = GatewayStatus.CONNECTED

    def _do_connect(self) -> bool:  # pragma: no cover - not exercised
        return True

    def _do_disconnect(self) -> None:  # pragma: no cover
        return None

    def _do_send_order(self, request: OrderRequest) -> str:
        return f"BROKER-{request.client_order_id}"

    def _do_cancel_order(self, broker_order_id: str) -> bool:  # pragma: no cover
        return True

    def _do_query_account(self):  # pragma: no cover
        return None

    def _do_query_positions(self):  # pragma: no cover
        return []

    def _do_query_orders(self):  # pragma: no cover
        return []


def test_send_order_registers_state_machine():
    gw = _DummyGateway()
    cid = gw.send_order("600519.SH", "buy", 100, price=1800.0)
    history = gw.order_state_history(cid)
    assert history, "send_order should record at least one transition"
    assert history[-1].to_state == OrderStatus.SUBMITTED


def test_on_order_update_invalid_transition_logged_not_raised(caplog):
    gw = _DummyGateway()
    cid = gw.send_order("600519.SH", "buy", 100, price=1800.0)
    # Drive to terminal then send another update; lenient mode should log.
    fill = OrderUpdate(
        client_order_id=cid,
        broker_order_id=gw._client_to_broker[cid],
        symbol="600519.SH",
        side=gw._orders[cid].side,
        status=OrderStatus.FILLED,
        quantity=100,
        filled_quantity=100,
    )
    gw._on_order_update(fill)
    assert gw._state_machine.is_terminal(cid)
    # Now a phantom SUBMITTED message — illegal but tolerated.
    phantom = OrderUpdate(
        client_order_id=cid,
        broker_order_id=gw._client_to_broker[cid],
        symbol="600519.SH",
        side=gw._orders[cid].side,
        status=OrderStatus.SUBMITTED,
        quantity=100,
    )
    with caplog.at_level("WARNING"):
        gw._on_order_update(phantom)
    # State remains terminal — illegal transition was rejected.
    assert gw._state_machine.current(cid) == OrderStatus.FILLED


def test_on_order_update_invalid_transition_strict_raises():
    gw = _DummyGateway()
    gw._strict_state_machine = True
    cid = gw.send_order("600519.SH", "buy", 100, price=1800.0)
    fill = OrderUpdate(
        client_order_id=cid,
        broker_order_id=gw._client_to_broker[cid],
        symbol="600519.SH",
        side=gw._orders[cid].side,
        status=OrderStatus.FILLED,
        quantity=100,
        filled_quantity=100,
    )
    gw._on_order_update(fill)
    phantom = OrderUpdate(
        client_order_id=cid,
        broker_order_id=gw._client_to_broker[cid],
        symbol="600519.SH",
        side=gw._orders[cid].side,
        status=OrderStatus.SUBMITTED,
        quantity=100,
    )
    # Strict mode propagates the illegal transition from both the direct
    # helper and the broker-callback path.
    with pytest.raises(InvalidOrderStateTransition):
        gw._transition_order(cid, OrderStatus.SUBMITTED, reason="phantom")
    with pytest.raises(InvalidOrderStateTransition):
        gw._on_order_update(phantom)


# ---------------------------------------------------------------------------
# _safe_call
# ---------------------------------------------------------------------------


def test_safe_call_returns_value_on_success():
    gw = _DummyGateway()
    assert gw._safe_call(lambda: 42) == 42


def test_safe_call_retries_then_succeeds():
    gw = _DummyGateway()
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("transient")
        return "ok"

    assert gw._safe_call(flaky, retry=3, backoff=0.0) == "ok"
    assert calls["n"] == 3


def test_safe_call_retries_exhausted_raises():
    gw = _DummyGateway()

    def always_fail():
        raise RuntimeError("nope")

    with pytest.raises(RuntimeError, match="nope"):
        gw._safe_call(always_fail, retry=2, backoff=0.0)


def test_safe_call_on_error_fallback_used():
    gw = _DummyGateway()

    def always_fail():
        raise RuntimeError("boom")

    result = gw._safe_call(
        always_fail, retry=1, backoff=0.0, on_error=lambda exc: "fallback"
    )
    assert result == "fallback"


def test_safe_call_missing_sdk_in_stub_mode_returns_none():
    gw = _DummyGateway(stub_mode=True)

    def needs_sdk():
        raise ImportError("xtquant not installed")

    assert gw._safe_call(needs_sdk) is None


def test_safe_call_missing_sdk_real_mode_raises_gateway_unavailable():
    gw = _DummyGateway(stub_mode=False)

    def needs_sdk():
        raise ModuleNotFoundError("xtp")

    with pytest.raises(GatewayUnavailable):
        gw._safe_call(needs_sdk)
