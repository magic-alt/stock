"""Shared order lifecycle state machine.

This module is the single implementation of order transition validation used
by OMS, paper trading, and live gateway adapters.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Optional, Set

if TYPE_CHECKING:
    from src.core.interfaces import OrderStatusEnum


class OrderStatus(str, Enum):
    """Gateway-facing order states for lifecycle validation."""

    PENDING_SUBMIT = "pending_submit"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    PARTIALLY_FILLED = "partial_fill"
    FILLED = "filled"
    CANCEL_PENDING = "cancel_pending"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    ERROR = "error"


class InvalidOrderStateTransition(Exception):
    """Raised when an illegal order state transition is attempted."""

    def __init__(self, client_order_id: str, from_state: OrderStatus, to_state: OrderStatus):
        super().__init__(
            f"Illegal order transition for {client_order_id}: {from_state.value} -> {to_state.value}"
        )
        self.client_order_id = client_order_id
        self.from_state = from_state
        self.to_state = to_state


@dataclass
class OrderStateTransition:
    """One transition record for the audit history."""

    client_order_id: str
    from_state: OrderStatus
    to_state: OrderStatus
    timestamp: datetime = field(default_factory=datetime.now)
    reason: str = ""


class OrderStateMachine:
    """Validate and record order state transitions across execution modes."""

    _TRANSITIONS: Dict[OrderStatus, Set[OrderStatus]] = {
        OrderStatus.PENDING_SUBMIT: {
            OrderStatus.SUBMITTED,
            OrderStatus.ACCEPTED,
            OrderStatus.REJECTED,
            OrderStatus.ERROR,
            OrderStatus.CANCELLED,
        },
        OrderStatus.SUBMITTED: {
            OrderStatus.ACCEPTED,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.CANCEL_PENDING,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED,
            OrderStatus.ERROR,
        },
        OrderStatus.ACCEPTED: {
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.CANCEL_PENDING,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED,
            OrderStatus.ERROR,
        },
        OrderStatus.PARTIALLY_FILLED: {
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.CANCEL_PENDING,
            OrderStatus.CANCELLED,
            OrderStatus.EXPIRED,
            OrderStatus.ERROR,
        },
        OrderStatus.CANCEL_PENDING: {
            OrderStatus.CANCELLED,
            OrderStatus.FILLED,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.REJECTED,
            OrderStatus.ERROR,
        },
        OrderStatus.FILLED: set(),
        OrderStatus.CANCELLED: set(),
        OrderStatus.REJECTED: set(),
        OrderStatus.EXPIRED: set(),
        OrderStatus.ERROR: set(),
    }

    TERMINAL_STATES: Set[OrderStatus] = {
        OrderStatus.FILLED,
        OrderStatus.CANCELLED,
        OrderStatus.REJECTED,
        OrderStatus.EXPIRED,
        OrderStatus.ERROR,
    }

    def __init__(self, history_limit: int = 1000):
        self._history: List[OrderStateTransition] = []
        self._current: Dict[str, OrderStatus] = {}
        self._lock = threading.Lock()
        self._history_limit = history_limit

    def register(self, client_order_id: str, initial: OrderStatus = OrderStatus.PENDING_SUBMIT) -> None:
        """Register a new order id with its initial state."""
        with self._lock:
            self._current[client_order_id] = initial

    def current(self, client_order_id: str) -> Optional[OrderStatus]:
        with self._lock:
            return self._current.get(client_order_id)

    def is_terminal(self, client_order_id: str) -> bool:
        cur = self.current(client_order_id)
        return cur in self.TERMINAL_STATES

    def can_transition(self, from_state: OrderStatus, to_state: OrderStatus) -> bool:
        allowed = self._TRANSITIONS.get(from_state, set())
        return to_state in allowed

    def transition(
        self,
        client_order_id: str,
        to_state: OrderStatus,
        reason: str = "",
        *,
        strict: bool = True,
    ) -> OrderStateTransition:
        """Move an order to ``to_state``, recording the transition."""
        with self._lock:
            current = self._current.get(client_order_id)
            if current is None:
                current = OrderStatus.PENDING_SUBMIT
                self._current[client_order_id] = current

            if current == to_state and to_state != OrderStatus.PARTIALLY_FILLED:
                rec = OrderStateTransition(
                    client_order_id=client_order_id,
                    from_state=current,
                    to_state=to_state,
                    reason=f"[noop] {reason}".strip(),
                )
                self._append_history(rec)
                return rec

            if not self.can_transition(current, to_state):
                if strict:
                    raise InvalidOrderStateTransition(client_order_id, current, to_state)
                rec = OrderStateTransition(
                    client_order_id=client_order_id,
                    from_state=current,
                    to_state=to_state,
                    reason=f"[rejected] {reason}".strip(),
                )
                self._append_history(rec)
                return rec

            self._current[client_order_id] = to_state
            rec = OrderStateTransition(
                client_order_id=client_order_id,
                from_state=current,
                to_state=to_state,
                reason=reason,
            )
            self._append_history(rec)
            return rec

    def history(self, client_order_id: Optional[str] = None) -> List[OrderStateTransition]:
        with self._lock:
            if client_order_id is None:
                return list(self._history)
            return [t for t in self._history if t.client_order_id == client_order_id]

    def _append_history(self, rec: OrderStateTransition) -> None:
        self._history.append(rec)
        if len(self._history) > self._history_limit:
            drop = max(1, self._history_limit // 10)
            del self._history[:drop]


def to_lifecycle_status(status: object) -> OrderStatus:
    """Map core/API status values onto the shared lifecycle state machine."""
    from src.core.interfaces import OrderStatusEnum, normalize_order_status

    canonical = normalize_order_status(status)  # type: ignore[arg-type]
    mapping = {
        OrderStatusEnum.CREATED: OrderStatus.PENDING_SUBMIT,
        OrderStatusEnum.SUBMITTED: OrderStatus.SUBMITTED,
        OrderStatusEnum.ACCEPTED: OrderStatus.ACCEPTED,
        OrderStatusEnum.PARTIALLY_FILLED: OrderStatus.PARTIALLY_FILLED,
        OrderStatusEnum.FILLED: OrderStatus.FILLED,
        OrderStatusEnum.CANCELLED: OrderStatus.CANCELLED,
        OrderStatusEnum.REJECTED: OrderStatus.REJECTED,
        OrderStatusEnum.EXPIRED: OrderStatus.EXPIRED,
    }
    return mapping[canonical]


def from_lifecycle_status(status: OrderStatus) -> "OrderStatusEnum":
    """Map state-machine states to canonical core/API status values."""
    from src.core.interfaces import OrderStatusEnum

    mapping = {
        OrderStatus.PENDING_SUBMIT: OrderStatusEnum.CREATED,
        OrderStatus.SUBMITTED: OrderStatusEnum.SUBMITTED,
        OrderStatus.ACCEPTED: OrderStatusEnum.ACCEPTED,
        OrderStatus.PARTIALLY_FILLED: OrderStatusEnum.PARTIALLY_FILLED,
        OrderStatus.FILLED: OrderStatusEnum.FILLED,
        OrderStatus.CANCEL_PENDING: OrderStatusEnum.SUBMITTED,
        OrderStatus.CANCELLED: OrderStatusEnum.CANCELLED,
        OrderStatus.REJECTED: OrderStatusEnum.REJECTED,
        OrderStatus.EXPIRED: OrderStatusEnum.EXPIRED,
        OrderStatus.ERROR: OrderStatusEnum.REJECTED,
    }
    return mapping[status]