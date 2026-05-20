"""Tests for the V6 platform kernel and component lifecycle FSM (Phase 1)."""
from __future__ import annotations

import threading

import pytest

from src.core.component_state import (
    ComponentState,
    InvalidStateTransition,
    Lifecycle,
    TransitionEvent,
    is_legal_transition,
)
from src.core.kernel import (
    LIFECYCLE_TOPIC,
    PlatformKernel,
    get_kernel,
    reset_kernel,
)
from src.core.message_bus import Message, MessageBus


# ---------------------------------------------------------------------------
# ComponentState / Lifecycle FSM
# ---------------------------------------------------------------------------


class TestComponentStateFSM:
    def test_initial_state_is_pre_initialized(self):
        lc = Lifecycle("a")
        assert lc.state is ComponentState.PRE_INITIALIZED
        assert not lc.is_running()
        assert not lc.is_terminal()

    def test_happy_path_transitions(self):
        lc = Lifecycle("a")
        lc.transition(ComponentState.READY)
        lc.transition(ComponentState.RUNNING)
        lc.transition(ComponentState.STOPPING)
        lc.transition(ComponentState.STOPPED)
        lc.transition(ComponentState.DISPOSED)
        assert lc.is_terminal()

    def test_illegal_skip_raises(self):
        lc = Lifecycle("a")
        # cannot skip READY
        with pytest.raises(InvalidStateTransition):
            lc.transition(ComponentState.RUNNING)

    def test_self_transition_is_illegal(self):
        lc = Lifecycle("a")
        lc.transition(ComponentState.READY)
        with pytest.raises(InvalidStateTransition):
            lc.transition(ComponentState.READY)

    def test_terminal_state_blocks_further_transitions(self):
        lc = Lifecycle("a")
        lc.transition(ComponentState.READY)
        lc.transition(ComponentState.DISPOSED)
        with pytest.raises(InvalidStateTransition):
            lc.transition(ComponentState.READY)

    def test_degraded_can_recover_or_stop(self):
        lc = Lifecycle("a")
        lc.transition(ComponentState.READY)
        lc.transition(ComponentState.RUNNING)
        lc.transition(ComponentState.DEGRADED)
        # recover
        lc.transition(ComponentState.RUNNING)
        # then degrade again and stop
        lc.transition(ComponentState.DEGRADED)
        lc.transition(ComponentState.STOPPING)
        lc.transition(ComponentState.STOPPED)

    def test_faulted_path_can_recover_to_stopped(self):
        lc = Lifecycle("a")
        lc.transition(ComponentState.READY)
        lc.transition(ComponentState.RUNNING)
        lc.transition(ComponentState.FAULTED)
        lc.transition(ComponentState.STOPPED)
        lc.transition(ComponentState.DISPOSED)

    def test_restart_after_stopped(self):
        lc = Lifecycle("a")
        lc.transition(ComponentState.READY)
        lc.transition(ComponentState.RUNNING)
        lc.transition(ComponentState.STOPPING)
        lc.transition(ComponentState.STOPPED)
        # STOPPED -> READY is allowed for restart
        lc.transition(ComponentState.READY)
        lc.transition(ComponentState.RUNNING)
        assert lc.is_running()

    def test_on_transition_callback_receives_event(self):
        captured: list[TransitionEvent] = []
        lc = Lifecycle("a", on_transition=captured.append)
        lc.transition(ComponentState.READY)
        lc.transition(ComponentState.RUNNING)
        assert len(captured) == 2
        assert captured[0].src is ComponentState.PRE_INITIALIZED
        assert captured[0].dst is ComponentState.READY
        assert captured[1].src is ComponentState.READY
        assert captured[1].dst is ComponentState.RUNNING

    def test_callback_exception_does_not_rollback(self):
        def boom(_event):
            raise RuntimeError("observer crashed")

        lc = Lifecycle("a", on_transition=boom)
        lc.transition(ComponentState.READY)
        assert lc.state is ComponentState.READY

    def test_is_legal_transition_helper(self):
        assert is_legal_transition(ComponentState.READY, ComponentState.RUNNING)
        assert not is_legal_transition(ComponentState.PRE_INITIALIZED, ComponentState.RUNNING)


# ---------------------------------------------------------------------------
# PlatformKernel
# ---------------------------------------------------------------------------


class _Recorder:
    def __init__(self, name: str, fail_start: bool = False, fail_stop: bool = False):
        self.name = name
        self.calls: list[str] = []
        self._fail_start = fail_start
        self._fail_stop = fail_stop

    def start(self):
        self.calls.append("start")
        if self._fail_start:
            raise RuntimeError(f"{self.name} start failed")

    def stop(self):
        self.calls.append("stop")
        if self._fail_stop:
            raise RuntimeError(f"{self.name} stop failed")


class TestPlatformKernel:
    def test_register_creates_ready_component(self):
        k = PlatformKernel()
        rec = _Recorder("a")
        k.register("a", rec, start=rec.start, stop=rec.stop)
        assert k.has("a")
        assert k.state_of("a") is ComponentState.READY
        assert k.names() == ["a"]
        assert k.get("a") is rec

    def test_duplicate_registration_rejected(self):
        k = PlatformKernel()
        k.register("a", _Recorder("a"))
        with pytest.raises(ValueError):
            k.register("a", _Recorder("a"))

    def test_empty_name_rejected(self):
        k = PlatformKernel()
        with pytest.raises(ValueError):
            k.register("", _Recorder("a"))

    def test_get_unknown_raises(self):
        k = PlatformKernel()
        with pytest.raises(KeyError):
            k.get("missing")

    def test_start_all_then_stop_all_lifo_order(self):
        k = PlatformKernel()
        order: list[str] = []

        def make_start(label: str):
            def _s():
                order.append(f"start:{label}")
            return _s

        def make_stop(label: str):
            def _s():
                order.append(f"stop:{label}")
            return _s

        for label in ("a", "b", "c"):
            k.register(label, object(), start=make_start(label), stop=make_stop(label))

        k.start_all()
        k.stop_all()
        assert order == [
            "start:a",
            "start:b",
            "start:c",
            "stop:c",
            "stop:b",
            "stop:a",
        ]

    def test_components_without_callbacks_transition_anyway(self):
        k = PlatformKernel()
        k.register("a", object())  # no start/stop
        k.start_all()
        assert k.state_of("a") is ComponentState.RUNNING
        k.stop_all()
        # No stop callback and STOPPING transition still requires explicit
        # progression; the kernel marks it STOPPED via stop_one.
        assert k.state_of("a") is ComponentState.STOPPED

    def test_start_failure_marks_faulted_and_raises(self):
        k = PlatformKernel()
        bad = _Recorder("bad", fail_start=True)
        k.register("bad", bad, start=bad.start, stop=bad.stop)
        with pytest.raises(RuntimeError):
            k.start_all()
        assert k.state_of("bad") is ComponentState.FAULTED

    def test_stop_failure_marks_faulted_but_continues(self):
        k = PlatformKernel()
        a = _Recorder("a")
        bad = _Recorder("bad", fail_stop=True)
        c = _Recorder("c")
        k.register("a", a, start=a.start, stop=a.stop)
        k.register("bad", bad, start=bad.start, stop=bad.stop)
        k.register("c", c, start=c.start, stop=c.stop)
        k.start_all()
        k.stop_all()  # must not raise
        assert k.state_of("bad") is ComponentState.FAULTED
        # The other components must still have been stopped despite the failure.
        assert "stop" in a.calls
        assert "stop" in c.calls
        assert k.state_of("a") is ComponentState.STOPPED
        assert k.state_of("c") is ComponentState.STOPPED

    def test_lifecycle_events_published_on_bus(self):
        bus = MessageBus(mode="inprocess")
        captured: list[Message] = []
        bus.subscribe(LIFECYCLE_TOPIC, captured.append)
        k = PlatformKernel(bus=bus)
        k.register("a", object())  # publishes PRE_INITIALIZED -> READY
        k.start_all()                # READY -> RUNNING
        k.stop_all()                 # RUNNING -> STOPPING -> STOPPED
        topics = [m.payload for m in captured]
        # First event is the registration READY transition.
        assert topics[0]["component"] == "a"
        assert topics[0]["to"] == ComponentState.READY.value
        states = [(p["from"], p["to"]) for p in topics]
        assert (ComponentState.PRE_INITIALIZED.value, ComponentState.READY.value) in states
        assert (ComponentState.READY.value, ComponentState.RUNNING.value) in states
        assert (ComponentState.RUNNING.value, ComponentState.STOPPING.value) in states
        assert (ComponentState.STOPPING.value, ComponentState.STOPPED.value) in states

    def test_error_events_published_on_failure(self):
        bus = MessageBus(mode="inprocess")
        errors: list[Message] = []
        bus.subscribe("kernel.component.error", errors.append)
        k = PlatformKernel(bus=bus)
        bad = _Recorder("bad", fail_start=True)
        k.register("bad", bad, start=bad.start, stop=bad.stop)
        with pytest.raises(RuntimeError):
            k.start_all()
        assert len(errors) == 1
        assert errors[0].payload["component"] == "bad"
        assert errors[0].payload["phase"] == "start"
        assert errors[0].payload["error_type"] == "RuntimeError"

    def test_idempotent_start_skips_running_components(self):
        k = PlatformKernel()
        r = _Recorder("a")
        k.register("a", r, start=r.start, stop=r.stop)
        k.start_all()
        k.start_all()  # second call must not invoke start again
        assert r.calls.count("start") == 1

    def test_dispose_all_moves_components_to_disposed(self):
        k = PlatformKernel()
        r = _Recorder("a")
        k.register("a", r, start=r.start, stop=r.stop)
        k.start_all()
        k.stop_all()
        k.dispose_all()
        assert k.state_of("a") is ComponentState.DISPOSED

    def test_shutdown_closes_bus(self):
        bus = MessageBus(mode="inprocess")
        k = PlatformKernel(bus=bus)
        k.register("a", object())
        k.start_all()
        k.shutdown()
        assert k.state_of("a") is ComponentState.DISPOSED


class TestKernelSingleton:
    def test_get_kernel_returns_same_instance(self):
        reset_kernel()
        try:
            a = get_kernel()
            b = get_kernel()
            assert a is b
        finally:
            reset_kernel()

    def test_reset_kernel_creates_fresh_instance(self):
        reset_kernel()
        try:
            a = get_kernel()
            reset_kernel()
            b = get_kernel()
            assert a is not b
        finally:
            reset_kernel()


class TestMessageBusAdditions:
    def test_publish_message_envelope_delivers_payload(self):
        bus = MessageBus(mode="inprocess")
        captured: list[Message] = []
        bus.subscribe("test.*", captured.append)
        msg = Message(topic="test.tick", payload={"price": 1.23}, source="unit")
        delivered = bus.publish_message(msg)
        assert delivered == 1
        assert captured[0].topic == "test.tick"
        assert captured[0].payload == {"price": 1.23}
        assert captured[0].source == "unit"

    def test_publish_message_preserves_existing_publish_api(self):
        # Regression: original publish(topic, payload) still works after V6 additions.
        bus = MessageBus(mode="inprocess")
        captured: list[Message] = []
        bus.subscribe("a.*", captured.append)
        bus.publish("a.b", {"x": 1}, source="legacy")
        assert captured[0].payload == {"x": 1}
        assert captured[0].source == "legacy"


def test_kernel_register_is_thread_safe():
    k = PlatformKernel()
    errors: list[BaseException] = []

    def worker(i: int):
        try:
            k.register(f"c{i}", object())
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert len(k.names()) == 20
