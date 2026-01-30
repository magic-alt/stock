"""
Tests for heartbeat monitoring utilities.
"""
import time

from src.core.events import EventEngine, EventType
from src.core.monitoring import HeartbeatEmitter, HeartbeatMonitor, run_with_heartbeat_monitor


def test_heartbeat_emitter_emits():
    events = EventEngine()
    received = []

    def handler(event):
        received.append(event)

    events.register(EventType.HEARTBEAT, handler)
    events.start()

    emitter = HeartbeatEmitter(events, interval=0.02, source="unit-test")
    emitter.start()

    deadline = time.time() + 0.3
    while time.time() < deadline and not received:
        time.sleep(0.01)

    emitter.stop()
    events.stop()

    assert received
    assert received[0].data.get("source") == "unit-test"


def test_heartbeat_monitor_timeout():
    events = EventEngine()
    events.start()

    timed_out = {"value": False}

    def on_timeout(source, age):
        timed_out["value"] = True

    monitor = HeartbeatMonitor(
        events,
        timeout=0.05,
        check_interval=0.01,
        sources=["unit-test"],
        on_timeout=on_timeout,
    )
    monitor.start()

    deadline = time.time() + 0.3
    while time.time() < deadline and not timed_out["value"]:
        time.sleep(0.01)

    monitor.stop()
    events.stop()

    assert timed_out["value"]


def test_run_with_heartbeat_monitor_restarts():
    events = EventEngine()
    events.start()

    calls = {"count": 0}

    def runner():
        calls["count"] += 1
        if calls["count"] == 1:
            raise ValueError("fail once")
        return "ok"

    result = run_with_heartbeat_monitor(
        runner,
        events=events,
        max_restarts=1,
    )

    events.stop()

    assert result == "ok"
    assert calls["count"] == 2
