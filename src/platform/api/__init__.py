"""
Modular API layer with router, middleware, and request validation.

Provides FastAPI-style patterns on top of the existing HTTP server:
- APIRouter: URL pattern matching with path parameter extraction
- RBACMiddleware: Subject resolution + permission enforcement
- RateLimiter: Token-bucket rate limiting per client
- RequestValidator: JSON schema validation for request bodies
- AuditMiddleware: Automatic audit logging for write operations
"""
from .router import APIRouter, Route, RequestContext, ResponseContext
from .middleware import (
    RBACMiddleware,
    RateLimiter,
    RequestValidator,
    AuditMiddleware,
)

__all__ = [
    "APIRouter",
    "Route",
    "RequestContext",
    "ResponseContext",
    "RBACMiddleware",
    "RateLimiter",
    "RequestValidator",
    "AuditMiddleware",
]
