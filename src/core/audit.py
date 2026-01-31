"""
Audit logging utilities with optional hash chaining.
"""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from hashlib import sha256
from typing import Any, Dict, Optional


def _to_builtin(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _to_builtin(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_builtin(v) for v in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return value


@dataclass
class AuditEvent:
    """Structured audit log event."""
    event_id: str
    timestamp: str
    actor: str
    action: str
    resource: str
    result: str
    details: Dict[str, Any]
    prev_hash: str = ""
    hash: str = ""


class AuditLogger:
    """Append-only audit log with optional hash chaining."""

    def __init__(self, path: str = "./logs/audit.log", chain_hash: bool = True) -> None:
        self.path = path
        self.chain_hash = chain_hash
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._last_hash = self._load_last_hash() if chain_hash else ""

    def log(
        self,
        *,
        actor: str,
        action: str,
        resource: str,
        result: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow().isoformat(timespec="seconds") + "Z",
            actor=actor,
            action=action,
            resource=resource,
            result=result,
            details=_to_builtin(details or {}),
            prev_hash=self._last_hash,
            hash="",
        )
        payload = asdict(event)
        payload["hash"] = self._compute_hash(payload)
        event.hash = payload["hash"]
        self._append(payload)
        if self.chain_hash:
            self._last_hash = event.hash
        return event

    def verify(self) -> bool:
        """Verify hash chain integrity."""
        if not self.chain_hash:
            return True
        prev_hash = ""
        if not os.path.exists(self.path):
            return True
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                expected_prev = record.get("prev_hash", "")
                if expected_prev != prev_hash:
                    return False
                expected_hash = record.get("hash", "")
                if expected_hash != self._compute_hash(record):
                    return False
                prev_hash = expected_hash
        return True

    def _append(self, payload: Dict[str, Any]) -> None:
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _load_last_hash(self) -> str:
        if not os.path.exists(self.path):
            return ""
        last = ""
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    last = record.get("hash", "")
                except json.JSONDecodeError:
                    continue
        return last

    @staticmethod
    def _compute_hash(payload: Dict[str, Any]) -> str:
        sanitized = dict(payload)
        sanitized["hash"] = ""
        blob = json.dumps(sanitized, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return sha256(blob.encode("utf-8")).hexdigest()


def audit_event(
    logger: Optional[AuditLogger],
    *,
    actor: str,
    action: str,
    resource: str,
    result: str,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Helper to emit audit event if logger provided."""
    if logger:
        logger.log(actor=actor, action=action, resource=resource, result=result, details=details)
