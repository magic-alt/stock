"""
Event Engine Module

Lightweight event-driven architecture inspired by vn.py's EventEngine.
Provides a thread-safe event bus for decoupling components.

Reference: https://github.com/vnpy/vnpy/blob/master/vnpy/event/engine.py
"""
from __future__ import annotations

from dataclasses import dataclass
from queue import Queue, Empty
from threading import Thread, Event as TEvent
from typing import Callable, Dict, List, Any, Protocol


@dataclass(slots=True)
class Event:
    """
    Event object containing event type and associated data.
    
    Attributes:
        type: Event type identifier (e.g., "data.loaded", "strategy.signal")
        data: Arbitrary data payload associated with the event
    """
    type: str
    data: Any = None


class Handler(Protocol):
    """Protocol for event handlers."""
    def __call__(self, event: Event) -> None:
        """Handle an event."""
        ...


class EventEngine:
    """
    Thread-safe event bus for publish-subscribe pattern.
    
    Features:
    - Non-blocking event publishing (queue-based)
    - Multiple handlers per event type
    - Thread-safe handler registration
    - Graceful shutdown
    
    Example:
        >>> engine = EventEngine()
        >>> engine.register("order.filled", lambda e: print(f"Order filled: {e.data}"))
        >>> engine.start()
        >>> engine.put(Event("order.filled", {"symbol": "600519.SH", "size": 100}))
        >>> engine.stop()
    """
    
    def __init__(self) -> None:
        """Initialize event engine."""
        self._q: Queue[Event] = Queue()
        self._handlers: Dict[str, List[Handler]] = {}
        self._stop = TEvent()
        self._t: Thread | None = None

    def register(self, etype: str, handler: Handler) -> None:
        """
        Register an event handler for a specific event type.
        
        Args:
            etype: Event type to listen for
            handler: Callable that accepts an Event object
        """
        self._handlers.setdefault(etype, []).append(handler)

    def unregister(self, etype: str, handler: Handler) -> None:
        """
        Unregister a specific event handler.
        
        Args:
            etype: Event type
            handler: Handler to remove
        """
        if etype in self._handlers:
            try:
                self._handlers[etype].remove(handler)
            except ValueError:
                pass

    def put(self, event: Event) -> None:
        """
        Publish an event to the queue (non-blocking).
        
        Args:
            event: Event object to publish
        """
        self._q.put(event)

    def start(self) -> None:
        """Start the event processing thread."""
        if self._t:
            return
        self._stop.clear()
        self._t = Thread(target=self._run, daemon=True, name="EventEngine")
        self._t.start()

    def stop(self) -> None:
        """Stop the event processing thread gracefully."""
        self._stop.set()
        if self._t:
            self._t.join(timeout=1.0)
            self._t = None

    def _run(self) -> None:
        """
        Event loop: fetch events from queue and dispatch to handlers.
        
        Runs in a separate thread until stop() is called.
        """
        while not self._stop.is_set():
            try:
                ev = self._q.get(timeout=0.2)
            except Empty:
                continue
            
            # Dispatch to all registered handlers
            for h in self._handlers.get(ev.type, []):
                try:
                    h(ev)
                except Exception as e:
                    # Swallow exceptions to prevent handler failures from crashing the engine
                    import warnings
                    warnings.warn(f"Event handler error for {ev.type}: {e}")


# Common event types (can be extended)
class EventType:
    """Standard event type constants."""
    
    # Data events
    DATA_LOADED = "data.loaded"
    DATA_ERROR = "data.error"
    
    # Strategy events
    STRATEGY_INIT = "strategy.init"
    STRATEGY_START = "strategy.start"
    STRATEGY_STOP = "strategy.stop"
    STRATEGY_SIGNAL = "strategy.signal"
    
    # Order events
    ORDER_SENT = "order.sent"
    ORDER_FILLED = "order.filled"
    ORDER_CANCELLED = "order.cancelled"
    ORDER_REJECTED = "order.rejected"
    ORDER = "order"  # V3.0: Generic order event from matching engine
    
    # Trade events
    TRADE_EXECUTED = "trade.executed"
    TRADE = "trade"  # V3.0: Generic trade event from matching engine
    
    # Position events
    POSITION_OPENED = "position.opened"
    POSITION_CLOSED = "position.closed"
    
    # Performance events
    METRICS_CALCULATED = "metrics.calculated"
    PARETO_COMPLETED = "pareto.completed"
    
    # Pipeline events
    PIPELINE_STAGE = "pipeline.stage"
    PIPELINE_PROGRESS = "pipeline.progress"
    PIPELINE_COMPLETED = "pipeline.completed"
    
    # Risk events
    RISK_WARNING = "risk.warning"
    RISK_BREACH = "risk.breach"
