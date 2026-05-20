"""V6 platform kernel — process-wide composition root.

The kernel owns the :class:`~src.core.message_bus.MessageBus`, a registry of
named components, and the lifecycle FSM for each one. It is the single
entry point that engines, adapters and runtimes will resolve dependencies
through once the V6 refactor lands.

Phase 1 scope (this module): introduce :class:`PlatformKernel`, component
registration, ordered start/stop, and lifecycle event publication. Engines
and adapters are *not* yet rewritten to depend on the kernel — that work
lands in Phases 3-4. This module is therefore additive: existing modules
keep working unchanged, and the kernel is opt-in for new code.

Design notes
------------

* **In-process by default.** The kernel creates a default ``MessageBus`` in
  ``inprocess`` mode. Cross-process backends (ZMQ, Redis) remain opt-in via
  ``PlatformKernel(bus=MessageBus(mode="zmq", ...))``.
* **Deterministic order.** Components are started in registration order and
  stopped in reverse order (LIFO). This mirrors Nautilus' boot/shutdown
  guarantees and lets adapters depend on engines that registered earlier.
* **Lifecycle events on the bus.** Every state transition publishes a
  ``kernel.component.state`` event so observability adapters can subscribe
  without coupling to internal APIs.
* **Singleton is opt-in.** ``get_kernel()`` returns a lazily created shared
  instance for code paths (CLI, API) that want one. Tests and embedded
  uses should instantiate ``PlatformKernel()`` directly.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .component_state import (
    ComponentState,
    InvalidStateTransition,
    Lifecycle,
    TransitionEvent,
)
from .message_bus import MessageBus


LIFECYCLE_TOPIC = "kernel.component.state"


@dataclass
class ComponentRecord:
    """Internal record kept by the kernel for each registered component."""

    name: str
    component: Any
    lifecycle: Lifecycle
    start: Optional[Callable[[], None]] = None
    stop: Optional[Callable[[], None]] = None
    tags: tuple = field(default_factory=tuple)


class PlatformKernel:
    """Process-wide composition root for the V6 open platform.

    The kernel is intentionally small and does not import any engine or
    adapter modules. It only owns three things:

    1. a :class:`MessageBus` instance,
    2. a name-indexed registry of components, and
    3. the lifecycle FSM for each component.

    Usage::

        kernel = PlatformKernel()
        kernel.register(
            name="data_engine",
            component=my_data_engine,
            start=my_data_engine.start,
            stop=my_data_engine.stop,
        )
        kernel.start_all()
        ...
        kernel.stop_all()
        kernel.dispose_all()
    """

    def __init__(self, bus: Optional[MessageBus] = None) -> None:
        self._bus = bus if bus is not None else MessageBus(mode="inprocess")
        self._components: Dict[str, ComponentRecord] = {}
        self._order: List[str] = []
        self._lock = threading.RLock()

    # ---- public API ----------------------------------------------------------

    @property
    def bus(self) -> MessageBus:
        return self._bus

    def register(
        self,
        name: str,
        component: Any,
        start: Optional[Callable[[], None]] = None,
        stop: Optional[Callable[[], None]] = None,
        tags: Optional[tuple] = None,
    ) -> ComponentRecord:
        """Register a component under ``name``.

        ``start`` and ``stop`` are optional callables. When omitted, the
        kernel only tracks the lifecycle FSM and the component is moved to
        ``READY`` immediately. Components without callbacks are useful for
        passive services (e.g. a config provider) that simply need a
        registered identity on the bus.
        """
        if not name or not isinstance(name, str):
            raise ValueError("Component name must be a non-empty string")
        with self._lock:
            if name in self._components:
                raise ValueError(f"Component '{name}' already registered")
            lc = Lifecycle(name=name, on_transition=self._publish_transition)
            record = ComponentRecord(
                name=name,
                component=component,
                lifecycle=lc,
                start=start,
                stop=stop,
                tags=tuple(tags) if tags else (),
            )
            self._components[name] = record
            self._order.append(name)
            lc.transition(ComponentState.READY)
            return record

    def get(self, name: str) -> Any:
        """Return the component instance registered under ``name``."""
        with self._lock:
            if name not in self._components:
                raise KeyError(f"No component registered as '{name}'")
            return self._components[name].component

    def state_of(self, name: str) -> ComponentState:
        """Return the current :class:`ComponentState` of ``name``."""
        with self._lock:
            if name not in self._components:
                raise KeyError(f"No component registered as '{name}'")
            return self._components[name].lifecycle.state

    def has(self, name: str) -> bool:
        with self._lock:
            return name in self._components

    def names(self) -> List[str]:
        """Return registered component names in registration order."""
        with self._lock:
            return list(self._order)

    def start_all(self) -> None:
        """Start every registered component in registration order.

        Components already in ``RUNNING`` or ``DEGRADED`` are skipped.
        Components without a ``start`` callback transition straight to
        ``RUNNING``. A start callback raising an exception transitions
        that component to ``FAULTED`` and re-raises after publishing the
        event; previously started components are NOT rolled back, mirroring
        Nautilus' fail-fast boot semantics. Callers may then invoke
        :meth:`stop_all` to unwind.
        """
        with self._lock:
            order = list(self._order)
        for name in order:
            self._start_one(name)

    def stop_all(self) -> None:
        """Stop components in reverse registration order (LIFO).

        Exceptions from stop callbacks are caught and logged via the bus
        (``kernel.component.error`` topic). Stop is best-effort: a failing
        component does not prevent later (earlier-registered) ones from
        stopping. This matches the operational guarantee that shutdown
        always completes.
        """
        with self._lock:
            order = list(reversed(self._order))
        for name in order:
            self._stop_one(name)

    def dispose_all(self) -> None:
        """Move every stopped/ready component to ``DISPOSED``.

        After ``dispose_all`` the kernel still holds references but the
        FSMs are terminal. A fresh kernel must be constructed to restart.
        """
        with self._lock:
            order = list(reversed(self._order))
        for name in order:
            rec = self._components.get(name)
            if rec is None:
                continue
            try:
                if rec.lifecycle.state in (ComponentState.READY, ComponentState.STOPPED, ComponentState.FAULTED):
                    rec.lifecycle.transition(ComponentState.DISPOSED)
            except InvalidStateTransition:
                # Already terminal or unreachable - skip silently.
                continue

    def shutdown(self) -> None:
        """Convenience: stop everything, dispose, close the bus."""
        self.stop_all()
        self.dispose_all()
        try:
            self._bus.close()
        except Exception:  # noqa: BLE001
            pass

    # ---- internal helpers ----------------------------------------------------

    def _start_one(self, name: str) -> None:
        rec = self._components.get(name)
        if rec is None:
            return
        if rec.lifecycle.state in (ComponentState.RUNNING, ComponentState.DEGRADED):
            return
        try:
            if rec.start is not None:
                rec.start()
            rec.lifecycle.transition(ComponentState.RUNNING)
        except Exception as exc:  # noqa: BLE001 - boundary
            try:
                rec.lifecycle.transition(ComponentState.FAULTED)
            except InvalidStateTransition:
                pass
            self._publish_error(name, "start", exc)
            raise

    def _stop_one(self, name: str) -> None:
        rec = self._components.get(name)
        if rec is None:
            return
        state = rec.lifecycle.state
        if state in (ComponentState.STOPPED, ComponentState.DISPOSED, ComponentState.PRE_INITIALIZED, ComponentState.READY):
            return
        try:
            rec.lifecycle.transition(ComponentState.STOPPING)
        except InvalidStateTransition:
            return
        try:
            if rec.stop is not None:
                rec.stop()
            rec.lifecycle.transition(ComponentState.STOPPED)
        except Exception as exc:  # noqa: BLE001 - boundary
            try:
                rec.lifecycle.transition(ComponentState.FAULTED)
            except InvalidStateTransition:
                pass
            self._publish_error(name, "stop", exc)

    def _publish_transition(self, event: TransitionEvent) -> None:
        payload = {
            "component": event.component,
            "from": event.src.value,
            "to": event.dst.value,
        }
        try:
            self._bus.publish(LIFECYCLE_TOPIC, payload, source="kernel")
        except Exception:  # noqa: BLE001 - observational
            pass

    def _publish_error(self, name: str, phase: str, exc: BaseException) -> None:
        payload = {
            "component": name,
            "phase": phase,
            "error_type": type(exc).__name__,
            "message": str(exc),
        }
        try:
            self._bus.publish("kernel.component.error", payload, source="kernel")
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# Optional process-wide singleton
# ---------------------------------------------------------------------------

_kernel_singleton: Optional[PlatformKernel] = None
_singleton_lock = threading.Lock()


def get_kernel() -> PlatformKernel:
    """Return a lazily created process-wide :class:`PlatformKernel`.

    Tests and embedded uses should construct their own instance instead.
    """
    global _kernel_singleton
    with _singleton_lock:
        if _kernel_singleton is None:
            _kernel_singleton = PlatformKernel()
        return _kernel_singleton


def reset_kernel() -> None:
    """Drop the process-wide kernel (for tests).

    Does NOT call :meth:`PlatformKernel.shutdown` — callers must handle
    cleanup of the prior instance if needed.
    """
    global _kernel_singleton
    with _singleton_lock:
        _kernel_singleton = None


__all__ = [
    "ComponentRecord",
    "LIFECYCLE_TOPIC",
    "PlatformKernel",
    "get_kernel",
    "reset_kernel",
]
