"""Compatibility alias for the canonical message bus adapter."""

from src.adapters.messaging.bus import InProcessBackend, Message, MessageBus, ZMQBackend

__all__ = ["InProcessBackend", "Message", "MessageBus", "ZMQBackend"]
