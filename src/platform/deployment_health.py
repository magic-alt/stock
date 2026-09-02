"""Deployment health contract for the FastAPI v2 service.

Gate 0 distinguishes process liveness from traffic readiness.  Liveness only
answers whether the API process can serve HTTP.  Readiness actively validates
mandatory runtime configuration/dependencies and returns HTTP 503 when the pod
or container must not receive traffic.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


_PROCESS_STARTED_AT = time.time()
_REMOTE_FALLBACK_BACKENDS = {"redis_fallback_json", "postgres_fallback_json"}


@dataclass(frozen=True)
class DependencyCheck:
    """One readiness dependency result."""

    name: str
    ready: bool
    detail: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _auth_check(app: FastAPI) -> DependencyCheck:
    settings = getattr(app.state, "api_auth_settings", None)
    if settings is None:
        return DependencyCheck(
            name="api_auth",
            ready=False,
            detail="API authentication settings are not initialized",
        )
    if bool(getattr(settings, "disabled", False)):
        return DependencyCheck(
            name="api_auth",
            ready=True,
            detail="authentication explicitly disabled for trusted local development",
            metadata={"mode": "disabled"},
        )
    if str(getattr(settings, "token", "")).strip():
        return DependencyCheck(
            name="api_auth",
            ready=True,
            detail="bootstrap Bearer credential configured",
            metadata={"mode": "bearer"},
        )
    return DependencyCheck(
        name="api_auth",
        ready=False,
        detail="PLATFORM_API_TOKEN is required while API authentication is enabled",
        metadata={"mode": "bearer"},
    )


def _job_store_check(app: FastAPI) -> DependencyCheck:
    queue = getattr(app.state, "job_queue", None)
    store = getattr(queue, "store", None)
    if store is None:
        return DependencyCheck(
            name="job_store",
            ready=False,
            detail="JobStore is not initialized",
        )

    backend_type = str(getattr(store, "backend_type", "unknown"))
    metadata: Dict[str, Any] = {"backend": backend_type}
    configured_path = getattr(store, "path", None)
    if configured_path:
        configured = str(configured_path)
        if "://" in configured:
            metadata["configured"] = configured.split("://", 1)[0] + "://***"
        else:
            metadata["configured"] = configured

    try:
        records = store.list()
        metadata["records"] = len(records)
    except Exception as exc:
        return DependencyCheck(
            name="job_store",
            ready=False,
            detail=f"JobStore probe failed: {exc}",
            metadata=metadata,
        )

    if backend_type in _REMOTE_FALLBACK_BACKENDS:
        return DependencyCheck(
            name="job_store",
            ready=False,
            detail="configured remote JobStore is running on local JSON fallback",
            metadata=metadata,
        )

    return DependencyCheck(
        name="job_store",
        ready=True,
        detail="JobStore probe succeeded",
        metadata=metadata,
    )


def _market_data_check(app: FastAPI) -> DependencyCheck:
    db_path = str(getattr(app.state, "local_market_data_db_path", ""))
    metadata: Dict[str, Any] = {"db_path": db_path}
    initialized = bool(getattr(app.state, "local_market_data_initialized", False))
    startup_error = str(getattr(app.state, "local_market_data_error", "") or "")

    if not initialized:
        return DependencyCheck(
            name="local_market_data",
            ready=False,
            detail=startup_error or "local DuckDB initialization did not complete",
            metadata=metadata,
        )

    try:
        from src.data_sources.duckdb_store import DuckDBConfig, DuckDBTimeSeriesStore

        store = DuckDBTimeSeriesStore(DuckDBConfig(db_path=db_path))
        try:
            stats = store.stats()
        finally:
            store.close()
        metadata["rows"] = int(stats.get("total_rows", 0) or 0)
    except Exception as exc:
        return DependencyCheck(
            name="local_market_data",
            ready=False,
            detail=f"local DuckDB probe failed: {exc}",
            metadata=metadata,
        )

    return DependencyCheck(
        name="local_market_data",
        ready=True,
        detail="local DuckDB probe succeeded",
        metadata=metadata,
    )


def build_readiness_report(app: FastAPI) -> Dict[str, Any]:
    """Return the current mandatory-dependency readiness report."""

    checks: List[DependencyCheck] = [
        _auth_check(app),
        _job_store_check(app),
        _market_data_check(app),
    ]
    ready = all(check.ready for check in checks)
    return {
        "ready": ready,
        "status": "ready" if ready else "not_ready",
        "version": app.version,
        "checks": {check.name: check.as_dict() for check in checks},
    }


def build_liveness_report(app: FastAPI) -> Dict[str, Any]:
    """Return process-only liveness without checking external dependencies."""

    return {
        "alive": True,
        "status": "alive",
        "version": app.version,
        "uptime_seconds": round(time.time() - _PROCESS_STARTED_AT, 3),
    }


def _remove_get_route(app: FastAPI, path: str) -> None:
    app.router.routes[:] = [
        route
        for route in app.router.routes
        if not (
            getattr(route, "path", None) == path
            and "GET" in (getattr(route, "methods", None) or set())
        )
    ]


def _move_new_routes_before_frontend_catchall(app: FastAPI, start_index: int) -> None:
    """Keep operational endpoints ahead of the SPA catch-all route."""

    new_routes = list(app.router.routes[start_index:])
    if not new_routes:
        return
    del app.router.routes[start_index:]
    insert_at = len(app.router.routes)
    for index, route in enumerate(app.router.routes):
        if getattr(route, "path", None) == "/{full_path:path}":
            insert_at = index
            break
    app.router.routes[insert_at:insert_at] = new_routes


def configure_deployment_health(app: FastAPI) -> FastAPI:
    """Install real liveness/readiness endpoints after API route registration."""

    if bool(getattr(app.state, "deployment_health_configured", False)):
        return app

    # api_v2 historically registered a readiness route that always returned
    # {"ready": true}. Replace it without requiring a monolithic router rewrite.
    _remove_get_route(app, "/api/v2/ready")
    start_index = len(app.router.routes)

    async def liveness(request: Request):
        return build_liveness_report(request.app)

    async def readiness(request: Request):
        report = build_readiness_report(request.app)
        if report["ready"]:
            return report
        return JSONResponse(status_code=503, content=report)

    app.add_api_route(
        "/api/v2/live",
        liveness,
        methods=["GET"],
        tags=["Operations"],
        summary="Process liveness",
        description="Returns 200 while the FastAPI process can serve HTTP; dependency failures do not fail liveness.",
        responses={200: {"description": "Process is alive"}},
    )
    app.add_api_route(
        "/api/v2/ready",
        readiness,
        methods=["GET"],
        tags=["Operations"],
        summary="Traffic readiness",
        description="Returns 503 until authentication configuration, JobStore, and local DuckDB are ready.",
        responses={
            200: {"description": "All mandatory dependencies are ready"},
            503: {"description": "One or more mandatory dependencies are not ready"},
        },
    )
    _move_new_routes_before_frontend_catchall(app, start_index)
    app.state.deployment_health_configured = True
    return app


__all__ = [
    "DependencyCheck",
    "build_liveness_report",
    "build_readiness_report",
    "configure_deployment_health",
]
