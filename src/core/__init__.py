"""Core module for event-driven architecture and gateway protocols."""

from .events import Event, EventEngine, EventType, Handler
from .gateway import (
    HistoryGateway,
    TradeGateway,
    BacktestGateway,
    PaperGateway,
    LiveGateway,
)

__all__ = [
    # Events
    "Event",
    "EventEngine",
    "EventType",
    "Handler",
    # Gateways
    "HistoryGateway",
    "TradeGateway",
    "BacktestGateway",
    "PaperGateway",
    "LiveGateway",
]
