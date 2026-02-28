"""
Message Bus (V5.0-E-2) — Cross-process event delivery with pluggable backends.

Provides:
- MessageBus: unified pub/sub interface
- InProcessBackend: threading-based (default, zero deps)
- ZMQBackend: ZeroMQ PUB/SUB for cross-process messaging (optional)
- RedisBackend: Redis PUB/SUB for distributed messaging (optional)

Usage:
    >>> from src.core.message_bus import MessageBus
    >>> bus = MessageBus(mode="inprocess")
    >>> bus.subscribe("tick.*", handler)
    >>> bus.publish("tick.600519", {"price": 1850.0})
"""
from __future__ import annotations

import fnmatch
import json
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set


# ---------------------------------------------------------------------------
# Message envelope
# ---------------------------------------------------------------------------

@dataclass
class Message:
    """Message envelope."""
    topic: str
    payload: Any
    timestamp: float = field(default_factory=time.time)
    source: str = ""

    def to_dict(self) -> dict:
        return {"topic": self.topic, "payload": self.payload, "ts": self.timestamp, "source": self.source}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, d: dict) -> "Message":
        return cls(topic=d["topic"], payload=d.get("payload"), timestamp=d.get("ts", 0), source=d.get("source", ""))


# ---------------------------------------------------------------------------
# InProcessBackend
# ---------------------------------------------------------------------------

class InProcessBackend:
    """Thread-safe in-process pub/sub."""

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._lock = threading.Lock()
        self._stats = {"published": 0, "delivered": 0, "errors": 0}

    def subscribe(self, pattern: str, handler: Callable) -> None:
        with self._lock:
            self._subscribers[pattern].append(handler)

    def unsubscribe(self, pattern: str, handler: Optional[Callable] = None) -> bool:
        with self._lock:
            if pattern not in self._subscribers:
                return False
            if handler is None:
                del self._subscribers[pattern]
            else:
                try:
                    self._subscribers[pattern].remove(handler)
                except ValueError:
                    return False
            return True

    def publish(self, topic: str, payload: Any, source: str = "") -> int:
        msg = Message(topic=topic, payload=payload, source=source)
        delivered = 0
        with self._lock:
            handlers = []
            for pattern, subs in self._subscribers.items():
                if fnmatch.fnmatch(topic, pattern):
                    handlers.extend(subs)

        self._stats["published"] += 1

        for handler in handlers:
            try:
                handler(msg)
                delivered += 1
                self._stats["delivered"] += 1
            except Exception:
                self._stats["errors"] += 1
        return delivered

    def stats(self) -> dict:
        return dict(self._stats)

    def close(self) -> None:
        with self._lock:
            self._subscribers.clear()


# ---------------------------------------------------------------------------
# ZMQBackend (optional)
# ---------------------------------------------------------------------------

class ZMQBackend:
    """ZeroMQ PUB/SUB backend for cross-process messaging.

    Requires: pyzmq (pip install pyzmq)
    """

    def __init__(self, pub_addr: str = "tcp://127.0.0.1:5555", sub_addr: str = "tcp://127.0.0.1:5556"):
        try:
            import zmq
        except ImportError:
            raise ImportError("ZMQ backend requires pyzmq: pip install pyzmq")
        self._zmq = zmq
        self._ctx = zmq.Context()
        self._pub_socket = self._ctx.socket(zmq.PUB)
        self._sub_socket = self._ctx.socket(zmq.SUB)
        self._pub_addr = pub_addr
        self._sub_addr = sub_addr
        self._handlers: Dict[str, List[Callable]] = defaultdict(list)
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stats = {"published": 0, "delivered": 0, "errors": 0}

    def bind(self) -> None:
        """Bind pub socket (server side)."""
        self._pub_socket.bind(self._pub_addr)

    def connect(self) -> None:
        """Connect sub socket (client side)."""
        self._sub_socket.connect(self._sub_addr)

    def subscribe(self, pattern: str, handler: Callable) -> None:
        self._handlers[pattern].append(handler)
        self._sub_socket.setsockopt_string(self._zmq.SUBSCRIBE, pattern.replace("*", ""))

    def unsubscribe(self, pattern: str, handler: Optional[Callable] = None) -> bool:
        if pattern not in self._handlers:
            return False
        if handler:
            try:
                self._handlers[pattern].remove(handler)
            except ValueError:
                return False
        else:
            del self._handlers[pattern]
        return True

    def publish(self, topic: str, payload: Any, source: str = "") -> int:
        msg = Message(topic=topic, payload=payload, source=source)
        self._pub_socket.send_string(f"{topic} {msg.to_json()}")
        self._stats["published"] += 1
        return 1

    def start_receiving(self) -> None:
        """Start background thread to receive messages."""
        self._running = True
        self._thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._thread.start()

    def _recv_loop(self) -> None:
        poller = self._zmq.Poller()
        poller.register(self._sub_socket, self._zmq.POLLIN)
        while self._running:
            socks = dict(poller.poll(100))
            if self._sub_socket in socks:
                raw = self._sub_socket.recv_string()
                parts = raw.split(" ", 1)
                if len(parts) == 2:
                    topic, json_str = parts
                    try:
                        msg = Message.from_dict(json.loads(json_str))
                    except Exception:
                        continue
                    for pattern, handlers in self._handlers.items():
                        if fnmatch.fnmatch(topic, pattern):
                            for h in handlers:
                                try:
                                    h(msg)
                                    self._stats["delivered"] += 1
                                except Exception:
                                    self._stats["errors"] += 1

    def stats(self) -> dict:
        return dict(self._stats)

    def close(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        self._pub_socket.close()
        self._sub_socket.close()
        self._ctx.term()


# ---------------------------------------------------------------------------
# MessageBus facade
# ---------------------------------------------------------------------------

class MessageBus:
    """Unified message bus with pluggable backends.

    Modes:
        inprocess — thread-safe, in-process (default)
        zmq — ZeroMQ PUB/SUB (requires pyzmq)
    """

    def __init__(self, mode: str = "inprocess", **kwargs):
        self.mode = mode
        if mode == "zmq":
            self._backend = ZMQBackend(**kwargs)
        else:
            self._backend = InProcessBackend()

    def subscribe(self, pattern: str, handler: Callable) -> None:
        self._backend.subscribe(pattern, handler)

    def unsubscribe(self, pattern: str, handler: Optional[Callable] = None) -> bool:
        return self._backend.unsubscribe(pattern, handler)

    def publish(self, topic: str, payload: Any, source: str = "") -> int:
        return self._backend.publish(topic, payload, source=source)

    def stats(self) -> dict:
        return self._backend.stats()

    def close(self) -> None:
        self._backend.close()


__all__ = ["Message", "MessageBus", "InProcessBackend", "ZMQBackend"]
