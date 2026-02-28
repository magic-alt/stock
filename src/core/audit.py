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
from typing import Any, Dict, List, Optional


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


    def archive(self) -> str:
        """Archive current log file and start a new one.

        Returns the path of the archived file.
        """
        if not os.path.exists(self.path):
            return ""
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S_%f")
        archived = f"{self.path}.{ts}.{uuid.uuid4().hex[:6]}.archived"
        os.rename(self.path, archived)
        self._last_hash = ""
        return archived

    def sign(self, secret_key: str) -> str:
        """Compute HMAC-SHA256 signature of the current log file."""
        import hmac
        if not os.path.exists(self.path):
            return ""
        with open(self.path, "rb") as f:
            content = f.read()
        return hmac.new(secret_key.encode("utf-8"), content, sha256).hexdigest()

    def verify_signature(self, secret_key: str, signature: str) -> bool:
        """Verify a previously produced HMAC signature."""
        import hmac
        return hmac.compare_digest(self.sign(secret_key), signature)

    def list_archives(self) -> List[str]:
        """Return sorted list of archived log file paths."""
        directory = os.path.dirname(self.path) or "."
        base = os.path.basename(self.path)
        archives: List[str] = []
        if not os.path.isdir(directory):
            return archives
        for fname in sorted(os.listdir(directory)):
            if fname.startswith(base + ".") and fname.endswith(".archived"):
                archives.append(os.path.join(directory, fname))
        return archives

    def apply_retention(self, policy: "RetentionPolicy") -> int:
        """Delete archived files exceeding retention policy. Returns count deleted."""
        archives = self.list_archives()
        deleted = 0
        # Max files: keep only the most recent
        while len(archives) > policy.max_files:
            oldest = archives.pop(0)
            try:
                os.remove(oldest)
                deleted += 1
            except OSError:
                pass
        # Max age
        import time as _time
        now = _time.time()
        remaining: List[str] = []
        for path in archives:
            try:
                age_days = (now - os.path.getmtime(path)) / 86400.0
                if age_days > policy.max_age_days:
                    os.remove(path)
                    deleted += 1
                else:
                    remaining.append(path)
            except OSError:
                remaining.append(path)
        return deleted

    def export_for_compliance(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> List["AuditEvent"]:
        """Export audit events within an optional date range."""
        if not os.path.exists(self.path):
            return []
        events: List[AuditEvent] = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts_str = record.get("timestamp", "")
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    ts = None
                if start and ts and ts < start.replace(tzinfo=ts.tzinfo):
                    continue
                if end and ts and ts > end.replace(tzinfo=ts.tzinfo):
                    continue
                events.append(AuditEvent(
                    event_id=record.get("event_id", ""),
                    timestamp=record.get("timestamp", ""),
                    actor=record.get("actor", ""),
                    action=record.get("action", ""),
                    resource=record.get("resource", ""),
                    result=record.get("result", ""),
                    details=record.get("details", {}),
                    prev_hash=record.get("prev_hash", ""),
                    hash=record.get("hash", ""),
                ))
        return events


@dataclass
class RetentionPolicy:
    """Configuration for audit log retention."""
    max_files: int = 10
    max_age_days: float = 90.0
    max_size_mb: float = 100.0


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
