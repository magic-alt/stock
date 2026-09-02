"""Authentication and authorization boundary for the FastAPI v2 surface.

Gate 0 keeps authentication deliberately small: a single bootstrap Bearer token
(`PLATFORM_API_TOKEN`) is mapped to the repository's existing RBAC ``Subject``
model.  Multi-user identity providers can replace the authenticator later
without changing route permissions or downstream audit semantics.
"""
from __future__ import annotations

import hmac
import os
import re
import threading
from dataclasses import dataclass
from typing import Optional, Pattern, Sequence

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.core.audit import AuditLogger, audit_event
from src.core.auth import Authorizer, Permission, Role, Subject
from src.core.logger import get_logger

logger = get_logger("platform.api_auth")


@dataclass(frozen=True)
class ApiAuthSettings:
    """Environment-backed bootstrap identity for FastAPI v2."""

    disabled: bool
    token: str
    subject_id: str
    role: str
    account_group: str
    strategy_id: str
    account_id: str
    audit_log_path: str


@dataclass(frozen=True)
class ProtectedRoute:
    method: str
    pattern: Pattern[str]
    permission: str
    audit_action: str
    audit_success: bool = False


_TRUE_VALUES = {"1", "true", "yes", "on"}


def _is_truthy(value: str) -> bool:
    return value.strip().lower() in _TRUE_VALUES


def load_api_auth_settings() -> ApiAuthSettings:
    """Resolve API authentication settings from environment variables."""

    return ApiAuthSettings(
        disabled=_is_truthy(os.environ.get("PLATFORM_API_AUTH_DISABLED", "0")),
        token=os.environ.get("PLATFORM_API_TOKEN", "").strip(),
        subject_id=os.environ.get("PLATFORM_API_TOKEN_SUBJECT", "bootstrap-admin").strip() or "bootstrap-admin",
        role=os.environ.get("PLATFORM_API_TOKEN_ROLE", Role.ADMIN).strip().lower() or Role.ADMIN,
        account_group=os.environ.get("PLATFORM_API_TOKEN_ACCOUNT_GROUP", "").strip(),
        strategy_id=os.environ.get("PLATFORM_API_TOKEN_STRATEGY_ID", "").strip(),
        account_id=os.environ.get("PLATFORM_API_TOKEN_ACCOUNT_ID", "").strip(),
        audit_log_path=os.environ.get("PLATFORM_AUDIT_LOG", "./logs/audit.log").strip() or "./logs/audit.log",
    )


def _route(method: str, path_regex: str, permission: str, action: str, *, audit: bool = False) -> ProtectedRoute:
    return ProtectedRoute(
        method=method.upper(),
        pattern=re.compile(path_regex),
        permission=permission,
        audit_action=action,
        audit_success=audit,
    )


# Route permissions are intentionally explicit.  Anonymous endpoints are those
# absent from this table (health/readiness/info/docs, strategy catalogue, public
# market-data reads and the static frontend).
PROTECTED_ROUTES: Sequence[ProtectedRoute] = (
    _route("POST", r"^/api/v2/local-data/update$", Permission.DATA_WRITE, "data.update", audit=True),
    _route("POST", r"^/api/v2/analysis/run$", Permission.RESEARCH_EXECUTE, "analysis.run", audit=True),
    _route("POST", r"^/api/v2/analysis/jobs$", Permission.RESEARCH_EXECUTE, "analysis.job.submit", audit=True),
    _route("GET", r"^/api/v2/analysis/jobs$", Permission.RESEARCH_EXECUTE, "analysis.job.list"),
    _route("GET", r"^/api/v2/analysis/jobs/[^/]+$", Permission.RESEARCH_EXECUTE, "analysis.job.get"),
    _route("POST", r"^/api/v2/strategies/validate$", Permission.RESEARCH_EXECUTE, "strategy.validate", audit=True),
    _route("POST", r"^/api/v2/strategies/run$", Permission.RESEARCH_EXECUTE, "strategy.run", audit=True),
    _route("POST", r"^/api/v2/backtest/run$", Permission.RESEARCH_EXECUTE, "backtest.run", audit=True),
    _route("POST", r"^/api/v2/backtest/jobs$", Permission.RESEARCH_EXECUTE, "backtest.job.submit", audit=True),
    _route("GET", r"^/api/v2/backtest/jobs$", Permission.RESEARCH_EXECUTE, "backtest.job.list"),
    _route("GET", r"^/api/v2/backtest/jobs/[^/]+$", Permission.RESEARCH_EXECUTE, "backtest.job.get"),
    _route("POST", r"^/api/v2/backtest/jobs/[^/]+/cancel$", Permission.JOB_MANAGE, "backtest.job.cancel", audit=True),
    _route("GET", r"^/api/v2/gateway/status$", Permission.ORDER_QUERY, "gateway.status"),
    _route("POST", r"^/api/v2/gateway/connect$", Permission.GATEWAY_CONNECT, "gateway.connect", audit=True),
    _route("POST", r"^/api/v2/gateway/disconnect$", Permission.GATEWAY_CONNECT, "gateway.disconnect", audit=True),
    _route("GET", r"^/api/v2/gateway/account$", Permission.ACCOUNT_QUERY, "gateway.account"),
    _route("GET", r"^/api/v2/gateway/positions$", Permission.POSITION_QUERY, "gateway.positions"),
    _route("GET", r"^/api/v2/gateway/orders$", Permission.ORDER_QUERY, "gateway.orders"),
    _route("GET", r"^/api/v2/gateway/trades$", Permission.ORDER_QUERY, "gateway.trades"),
    _route("GET", r"^/api/v2/gateway/snapshot$", Permission.ORDER_QUERY, "gateway.snapshot"),
    _route("POST", r"^/api/v2/gateway/order$", Permission.GATEWAY_TRADE, "gateway.order.submit", audit=True),
    _route("POST", r"^/api/v2/gateway/cancel$", Permission.GATEWAY_TRADE, "gateway.order.cancel", audit=True),
    _route("POST", r"^/api/v2/gateway/price$", Permission.GATEWAY_TRADE, "gateway.price.update", audit=True),
    _route("POST", r"^/api/v2/accounts$", Permission.ACCOUNT_MANAGE, "account.create", audit=True),
    _route("GET", r"^/api/v2/accounts$", Permission.ACCOUNT_QUERY, "account.list"),
    _route("GET", r"^/api/v2/accounts/[^/]+/risk$", Permission.ACCOUNT_QUERY, "account.risk"),
    _route("POST", r"^/api/v2/accounts/transfer$", Permission.FUND_TRANSFER, "account.transfer", audit=True),
    _route(
        "POST",
        r"^/api/v2/portfolio/capital-allocation/preview$",
        Permission.PORTFOLIO_ALLOCATE,
        "portfolio.capital_allocation.preview",
        audit=True,
    ),
    _route("GET", r"^/api/v2/metrics$", Permission.MONITOR_QUERY, "monitor.metrics"),
    _route("GET", r"^/api/v2/monitor/summary$", Permission.MONITOR_QUERY, "monitor.summary"),
    _route("GET", r"^/api/v2/monitor/history$", Permission.MONITOR_QUERY, "monitor.history"),
    _route("GET", r"^/api/v2/monitor/alerts$", Permission.MONITOR_QUERY, "monitor.alerts"),
    _route("GET", r"^/api/v2/demo/paper-trading$", Permission.RESEARCH_EXECUTE, "demo.paper_trading", audit=True),
)


def _match_route(method: str, path: str) -> Optional[ProtectedRoute]:
    upper_method = method.upper()
    for rule in PROTECTED_ROUTES:
        if rule.method == upper_method and rule.pattern.fullmatch(path):
            return rule
    return None


def _bootstrap_subject(settings: ApiAuthSettings) -> Subject:
    return Subject(
        subject_id=settings.subject_id,
        role=settings.role,
        account_group=settings.account_group,
        strategy_id=settings.strategy_id,
        account_id=settings.account_id,
    )


def _bearer_token(request: Request) -> Optional[str]:
    header = request.headers.get("Authorization", "").strip()
    if not header:
        return None
    scheme, separator, token = header.partition(" ")
    if not separator or scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def _error(status_code: int, detail: str, *, authenticate: bool = False) -> JSONResponse:
    headers = {"WWW-Authenticate": "Bearer"} if authenticate else None
    return JSONResponse(status_code=status_code, content={"detail": detail}, headers=headers)


def _audit(
    app: FastAPI,
    *,
    actor: str,
    action: str,
    resource: str,
    result: str,
    request: Request,
    permission: str,
    reason: str = "",
) -> None:
    logger_obj = getattr(app.state, "api_auth_audit_logger", None)
    if logger_obj is None:
        return
    details = {
        "method": request.method,
        "path": request.url.path,
        "permission": permission,
        "request_id": getattr(request.state, "request_id", request.headers.get("X-Request-ID", "")),
        "trace_id": getattr(request.state, "trace_id", request.headers.get("X-Trace-ID", "")),
    }
    if reason:
        details["reason"] = reason
    lock = getattr(app.state, "api_auth_audit_lock", None)
    if lock is None:
        audit_event(logger_obj, actor=actor, action=action, resource=resource, result=result, details=details)
        return
    with lock:
        audit_event(logger_obj, actor=actor, action=action, resource=resource, result=result, details=details)


def _install_openapi_security(app: FastAPI) -> None:
    """Document the middleware-enforced Bearer contract in OpenAPI."""

    original_openapi = app.openapi

    def openapi_with_security():
        schema = original_openapi()
        components = schema.setdefault("components", {})
        security_schemes = components.setdefault("securitySchemes", {})
        security_schemes["BearerAuth"] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "opaque",
            "description": "FastAPI v2 bootstrap Bearer token (PLATFORM_API_TOKEN).",
        }
        for path, path_item in schema.get("paths", {}).items():
            for method, operation in path_item.items():
                if method.upper() not in {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}:
                    continue
                rule = _match_route(method, path)
                if rule is None or not isinstance(operation, dict):
                    continue
                operation["security"] = [{"BearerAuth": []}]
                responses = operation.setdefault("responses", {})
                responses.setdefault("401", {"description": "Missing or invalid Bearer token"})
                responses.setdefault("403", {"description": "Authenticated subject lacks the required permission"})
        return schema

    app.openapi = openapi_with_security  # type: ignore[method-assign]


def configure_api_auth(app: FastAPI) -> FastAPI:
    """Install Bearer authentication, RBAC authorization and audit propagation."""

    settings = load_api_auth_settings()
    app.state.api_auth_settings = settings
    app.state.api_authorizer = Authorizer()
    app.state.api_auth_audit_logger = AuditLogger(settings.audit_log_path, chain_hash=True)
    app.state.api_auth_audit_lock = threading.Lock()

    if settings.disabled:
        logger.warning("fastapi_v2_auth_disabled", reason="PLATFORM_API_AUTH_DISABLED")
    elif not settings.token:
        logger.error("fastapi_v2_auth_token_missing", env="PLATFORM_API_TOKEN")

    @app.middleware("http")
    async def authenticate_and_authorize(request: Request, call_next):
        rule = _match_route(request.method, request.url.path)
        if rule is None:
            return await call_next(request)

        if settings.disabled:
            subject = Subject(subject_id="local-dev", role=Role.SYSTEM)
            request.state.auth_subject = subject
            request.state.auth_permission = rule.permission
            response = await call_next(request)
            if rule.audit_success:
                _audit(
                    app,
                    actor=subject.subject_id,
                    action=rule.audit_action,
                    resource=request.url.path,
                    result="success" if response.status_code < 400 else "error",
                    request=request,
                    permission=rule.permission,
                    reason="auth_disabled_local_dev",
                )
            return response

        if not settings.token:
            _audit(
                app,
                actor="anonymous",
                action=rule.audit_action,
                resource=request.url.path,
                result="denied",
                request=request,
                permission=rule.permission,
                reason="api_token_not_configured",
            )
            return _error(
                503,
                "API authentication is enabled but PLATFORM_API_TOKEN is not configured",
            )

        token = _bearer_token(request)
        if token is None:
            _audit(
                app,
                actor="anonymous",
                action=rule.audit_action,
                resource=request.url.path,
                result="denied",
                request=request,
                permission=rule.permission,
                reason="missing_or_malformed_bearer",
            )
            return _error(401, "Not authenticated", authenticate=True)

        if not hmac.compare_digest(token, settings.token):
            _audit(
                app,
                actor="anonymous",
                action=rule.audit_action,
                resource=request.url.path,
                result="denied",
                request=request,
                permission=rule.permission,
                reason="invalid_bearer_token",
            )
            return _error(401, "Invalid authentication credentials", authenticate=True)

        subject = _bootstrap_subject(settings)
        request.state.auth_subject = subject
        request.state.auth_permission = rule.permission
        try:
            app.state.api_authorizer.require(rule.permission, subject)
        except PermissionError as exc:
            _audit(
                app,
                actor=subject.subject_id,
                action=rule.audit_action,
                resource=request.url.path,
                result="denied",
                request=request,
                permission=rule.permission,
                reason=str(exc),
            )
            return _error(403, "Forbidden")

        response = await call_next(request)
        if rule.audit_success:
            _audit(
                app,
                actor=subject.subject_id,
                action=rule.audit_action,
                resource=request.url.path,
                result="success" if response.status_code < 400 else "error",
                request=request,
                permission=rule.permission,
            )
        return response

    _install_openapi_security(app)
    return app


__all__ = [
    "ApiAuthSettings",
    "ProtectedRoute",
    "PROTECTED_ROUTES",
    "configure_api_auth",
    "load_api_auth_settings",
]
