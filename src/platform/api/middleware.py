"""
API middleware components: RBAC, rate limiting, request validation, audit.
"""
from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

from src.core.auth import Authorizer, Permission, Role, Subject
from src.core.audit import AuditLogger

from .router import RequestContext, ResponseContext, Handler


# ---------------------------------------------------------------------------
# RBACMiddleware
# ---------------------------------------------------------------------------

class RBACMiddleware:
    """Resolves Bearer tokens to Subject and enforces permissions."""

    def __init__(
        self,
        authorizer: Authorizer,
        token_store: Optional[Dict[str, Subject]] = None,
        public_paths: Optional[Set[str]] = None,
    ) -> None:
        self.authorizer = authorizer
        self._token_store = token_store or {}
        self._public_paths: Set[str] = public_paths or set()

    def register_token(self, token: str, subject: Subject) -> None:
        self._token_store[token] = subject

    def is_public(self, path: str) -> bool:
        for pp in self._public_paths:
            if path == pp or path.startswith(pp + "/"):
                return True
        return False

    def __call__(self, handler: Handler) -> Handler:
        def wrapped(request: RequestContext) -> ResponseContext:
            if self.is_public(request.path):
                return handler(request)

            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return ResponseContext(status_code=401, body={"error": "Missing or invalid token"})

            token = auth_header[7:].strip()
            subject = self._token_store.get(token)
            if subject is None:
                return ResponseContext(status_code=401, body={"error": "Invalid token"})

            method = request.method.upper()
            if method in ("POST", "PUT", "DELETE"):
                required_perm = Permission.ORDER_SUBMIT
            else:
                required_perm = Permission.ORDER_QUERY

            if not self.authorizer.has_permission(required_perm, subject):
                return ResponseContext(status_code=403, body={"error": "Insufficient permissions"})

            request.subject = subject
            return handler(request)
        return wrapped


# ---------------------------------------------------------------------------
# RateLimiter (Token Bucket)
# ---------------------------------------------------------------------------

class RateLimiter:
    """Token-bucket rate limiter keyed by client identifier."""

    def __init__(self, max_tokens: int = 100, refill_rate: float = 10.0) -> None:
        self.max_tokens = max_tokens
        self.refill_rate = refill_rate
        self._buckets: Dict[str, Dict[str, float]] = {}
        self._lock = threading.Lock()

    def _get_bucket(self, client_id: str) -> Dict[str, float]:
        now = time.monotonic()
        with self._lock:
            if client_id not in self._buckets:
                self._buckets[client_id] = {"tokens": float(self.max_tokens), "last": now}
            bucket = self._buckets[client_id]
            elapsed = now - bucket["last"]
            bucket["tokens"] = min(self.max_tokens, bucket["tokens"] + elapsed * self.refill_rate)
            bucket["last"] = now
            return bucket

    def allow(self, client_id: str = "default") -> bool:
        bucket = self._get_bucket(client_id)
        with self._lock:
            if bucket["tokens"] >= 1.0:
                bucket["tokens"] -= 1.0
                return True
            return False

    def __call__(self, handler: Handler) -> Handler:
        def wrapped(request: RequestContext) -> ResponseContext:
            client_id = request.headers.get("X-Client-Id", "default")
            if not self.allow(client_id):
                return ResponseContext(status_code=429, body={"error": "Rate limit exceeded"})
            return handler(request)
        return wrapped


# ---------------------------------------------------------------------------
# RequestValidator
# ---------------------------------------------------------------------------

class RequestValidator:
    """Simple JSON schema validator for request bodies."""

    def __init__(self, required_fields: Optional[Dict[str, type]] = None) -> None:
        self._required: Dict[str, type] = required_fields or {}

    def validate(self, body: Optional[Dict[str, Any]]) -> Optional[str]:
        if not self._required:
            return None
        if body is None:
            return "Request body is required"
        for field_name, field_type in self._required.items():
            if field_name not in body:
                return f"Missing required field: {field_name}"
            if not isinstance(body[field_name], field_type):
                return f"Invalid type for {field_name}: expected {field_type.__name__}"
        return None

    def __call__(self, handler: Handler) -> Handler:
        def wrapped(request: RequestContext) -> ResponseContext:
            error = self.validate(request.body)
            if error:
                return ResponseContext(status_code=400, body={"error": error})
            return handler(request)
        return wrapped


# ---------------------------------------------------------------------------
# AuditMiddleware
# ---------------------------------------------------------------------------

class AuditMiddleware:
    """Logs write operations to audit trail."""

    WRITE_METHODS = {"POST", "PUT", "DELETE", "PATCH"}

    def __init__(self, audit_logger: AuditLogger) -> None:
        self._audit = audit_logger

    def __call__(self, handler: Handler) -> Handler:
        def wrapped(request: RequestContext) -> ResponseContext:
            response = handler(request)
            if request.method.upper() in self.WRITE_METHODS:
                actor = "anonymous"
                if request.subject and hasattr(request.subject, "subject_id"):
                    actor = request.subject.subject_id
                self._audit.log(
                    actor=actor,
                    action=f"api.{request.method.lower()}",
                    resource=request.path,
                    result="ok" if response.status_code < 400 else "error",
                    details={"status_code": response.status_code},
                )
            return response
        return wrapped
