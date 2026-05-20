"""Component lifecycle finite-state machine for the V6 platform kernel.

Every engine, adapter, gateway and runtime registered with the
:class:`~src.core.kernel.PlatformKernel` transitions through a fixed FSM
inspired by Nautilus Trader's ``ComponentState``:

    PRE_INITIALIZED -> READY -> RUNNING -> STOPPING -> STOPPED -> DISPOSED

Two off-path states cover failure modes:

    * ``DEGRADED`` — component is still running but reporting non-fatal issues
    * ``FAULTED``  — component has crashed and must be stopped/disposed

The FSM intentionally only enforces transition legality; it does NOT itself
perform any I/O. The :class:`Lifecycle` mixin lets a component embed the FSM
without inheritance restrictions, and an ``on_transition`` hook lets the
kernel publish ``kernel.component.state`` events on the message bus.

This module is part of Phase 1 of the V6 open-platform refactor and is
additive: nothing in :mod:`src.core` depends on it yet, and importing it
does not change the behaviour of existing modules.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional, Set, Tuple


class ComponentState(str, Enum):
    """Lifecycle states for a kernel-managed component.

    Inherits from ``str`` so the enum members serialise naturally in JSON
    payloads published on the message bus.
    """

    PRE_INITIALIZED = "PRE_INITIALIZED"
    READY = "READY"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    DISPOSED = "DISPOSED"
    DEGRADED = "DEGRADED"
    FAULTED = "FAULTED"


# Legal forward transitions. Any transition not listed here is rejected by
# ``Lifecycle.transition``. Self-transitions (e.g. RUNNING -> RUNNING) are
# explicitly NOT legal — callers must use ``on_degraded`` / ``on_fault`` or
# remain in the current state.
_LEGAL_TRANSITIONS: Set[Tuple[ComponentState, ComponentState]] = {
    (ComponentState.PRE_INITIALIZED, ComponentState.READY),
    (ComponentState.PRE_INITIALIZED, ComponentState.FAULTED),
    (ComponentState.READY, ComponentState.RUNNING),
    (ComponentState.READY, ComponentState.DISPOSED),
    (ComponentState.READY, ComponentState.FAULTED),
    (ComponentState.RUNNING, ComponentState.STOPPING),
    (ComponentState.RUNNING, ComponentState.DEGRADED),
    (ComponentState.RUNNING, ComponentState.FAULTED),
    (ComponentState.DEGRADED, ComponentState.RUNNING),
    (ComponentState.DEGRADED, ComponentState.STOPPING),
    (ComponentState.DEGRADED, ComponentState.FAULTED),
    (ComponentState.STOPPING, ComponentState.STOPPED),
    (ComponentState.STOPPING, ComponentState.FAULTED),
    (ComponentState.STOPPED, ComponentState.READY),  # allow restart
    (ComponentState.STOPPED, ComponentState.DISPOSED),
    (ComponentState.FAULTED, ComponentState.STOPPING),
    (ComponentState.FAULTED, ComponentState.STOPPED),
    (ComponentState.FAULTED, ComponentState.DISPOSED),
}


# Terminal state: no further transitions allowed.
_TERMINAL: Set[ComponentState] = {ComponentState.DISPOSED}


def is_legal_transition(src: ComponentState, dst: ComponentState) -> bool:
    """Return ``True`` if ``src -> dst`` is a legal FSM transition."""
    return (src, dst) in _LEGAL_TRANSITIONS


class InvalidStateTransition(RuntimeError):
    """Raised when an illegal :class:`ComponentState` transition is attempted."""

    def __init__(self, name: str, src: ComponentState, dst: ComponentState):
        super().__init__(
            f"Illegal state transition for component '{name}': {src.value} -> {dst.value}"
        )
        self.component = name
        self.src = src
        self.dst = dst


@dataclass
class TransitionEvent:
    """Payload published on the bus when a component transitions."""

    component: str
    src: ComponentState
    dst: ComponentState


class Lifecycle:
    """Mixin-style FSM holder.

    Components compose this object instead of inheriting from it so that the
    FSM stays orthogonal to a component's own class hierarchy. The kernel
    creates one ``Lifecycle`` per registered component and routes the
    ``on_transition`` callback to publish events on the message bus.
    """

    def __init__(
        self,
        name: str,
        on_transition: Optional[Callable[[TransitionEvent], None]] = None,
    ) -> None:
        self._name = name
        self._state = ComponentState.PRE_INITIALIZED
        self._on_transition = on_transition
        self._lock = threading.RLock()

    @property
    def name(self) -> str:
        return self._name

    @property
    def state(self) -> ComponentState:
        return self._state

    def transition(self, dst: ComponentState) -> None:
        """Move to ``dst`` if the transition is legal; raise otherwise.

        Emits a :class:`TransitionEvent` to the registered ``on_transition``
        callback after the state changes. Exceptions raised by the callback
        do not roll back the transition — the callback is observational only.
        """
        with self._lock:
            if self._state in _TERMINAL:
                raise InvalidStateTransition(self._name, self._state, dst)
            if not is_legal_transition(self._state, dst):
                raise InvalidStateTransition(self._name, self._state, dst)
            src = self._state
            self._state = dst
            event = TransitionEvent(component=self._name, src=src, dst=dst)
        if self._on_transition is not None:
            try:
                self._on_transition(event)
            except Exception:  # noqa: BLE001 - observational, never propagate
                pass

    # ---- convenience helpers -------------------------------------------------

    def is_running(self) -> bool:
        return self._state in (ComponentState.RUNNING, ComponentState.DEGRADED)

    def is_terminal(self) -> bool:
        return self._state in _TERMINAL


__all__ = [
    "ComponentState",
    "InvalidStateTransition",
    "Lifecycle",
    "TransitionEvent",
    "is_legal_transition",
]
