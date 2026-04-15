"""
FastAPI-based API server v2 (V5.0-C-1).

Provides async REST + WebSocket endpoints alongside the legacy ThreadingHTTPServer.
Features: auto OpenAPI docs, Pydantic validation, OAuth2 support, async handlers.
"""
from __future__ import annotations

import os
import time
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.logger import get_logger
from src.platform.api_server import APIMetrics, GatewayService, MonitorService
from src.platform.job_queue import JobQueue, JobStore

logger = get_logger("platform.api_v2")

try:
    from fastapi import FastAPI, HTTPException, Depends, Request, Response
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse, JSONResponse
    from pydantic import BaseModel, Field
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


# ---------------------------------------------------------------------------
# Pydantic models (request/response schemas)
# ---------------------------------------------------------------------------

if HAS_FASTAPI:

    PROJECT_ROOT = Path(__file__).resolve().parents[2]

    class ApiEnvelope(BaseModel):
        """Standard API response envelope."""
        ok: bool = True
        data: Optional[Any] = None
        error: Optional[str] = None
        request_id: Optional[str] = None

    class HealthResponse(BaseModel):
        status: str = "healthy"
        version: str = "5.0"
        uptime_seconds: float = 0.0

    class BacktestRequest(BaseModel):
        strategy: str = Field(..., description="Strategy name from the registry")
        symbols: List[str] = Field(..., min_length=1, description="List of symbol codes")
        start: str = Field("2024-01-01", description="Start date YYYY-MM-DD")
        end: str = Field("2024-12-31", description="End date YYYY-MM-DD")
        params: Dict[str, Any] = Field(default_factory=dict, description="Strategy parameters")
        cash: float = Field(100000, gt=0, description="Initial cash")
        commission: float = Field(0.001, ge=0, le=0.1, description="Commission rate")
        slippage: float = Field(0.001, ge=0, le=0.1, description="Slippage rate")

    class StrategyValidateRequest(BaseModel):
        code: str = Field(..., min_length=1, description="Python strategy code")

    class OrderRequest(BaseModel):
        symbol: str = Field(..., min_length=1)
        side: str = Field(..., pattern="^(buy|sell)$")
        quantity: float = Field(..., gt=0)
        price: Optional[float] = Field(None, ge=0)
        order_type: str = Field("limit", pattern="^(market|limit|stop|stop_limit)$")

    class ConnectRequest(BaseModel):
        mode: str = "paper"
        broker: str = "paper"
        host: str = ""
        port: int = 0
        api_key: str = ""
        secret: str = ""
        account: str = ""
        password: str = ""
        initial_cash: float = 1000000
        commission_rate: float = 0.0003
        slippage: float = 0.0001
        enable_risk_check: bool = True
        terminal_type: str = "QMT"
        terminal_path: str = ""
        trade_server: str = ""
        quote_server: str = ""
        client_id: int = 1
        td_front: str = ""
        md_front: str = ""
        broker_options: Dict[str, Any] = Field(default_factory=dict)

    class CancelRequest(BaseModel):
        order_id: str = Field(..., min_length=1)

    class PriceUpdateRequest(BaseModel):
        symbol: str = Field(..., min_length=1)
        price: float = Field(..., gt=0)

    # ------------------------------------------------------------------
    # Application factory
    # ------------------------------------------------------------------

    _start_time = time.time()

    def _resolve_allowed_origins(allowed_origins: Optional[List[str]]) -> List[str]:
        if allowed_origins is not None:
            return allowed_origins
        env_value = os.environ.get("PLATFORM_ALLOWED_ORIGINS", "").strip()
        if env_value:
            return [item.strip() for item in env_value.split(",") if item.strip()]
        return ["http://localhost:3000"]

    def _resolve_frontend_dist() -> Optional[Path]:
        raw_path = os.environ.get("PLATFORM_FRONTEND_DIST", "").strip()
        frontend_dist = Path(raw_path) if raw_path else PROJECT_ROOT / "frontend" / "dist"
        index_file = frontend_dist / "index.html"
        if frontend_dist.is_dir() and index_file.is_file():
            return frontend_dist.resolve()
        return None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("fastapi_starting")
        yield
        try:
            app.state.job_queue.shutdown()
        except Exception:
            logger.warning("fastapi_job_queue_shutdown_failed")
        logger.info("fastapi_stopping")

    def create_app(
        *,
        enable_cors: bool = True,
        allowed_origins: Optional[List[str]] = None,
    ) -> FastAPI:
        """Create and configure the FastAPI application."""
        app = FastAPI(
            title="Unified Quant Platform",
            description="V5.0 quantitative trading & backtesting platform API",
            version="5.0.0",
            docs_url="/api/v2/docs",
            redoc_url="/api/v2/redoc",
            openapi_url="/api/v2/openapi.json",
            lifespan=lifespan,
        )

        app.state.job_queue = JobQueue(
            store=JobStore(path=os.environ.get("PLATFORM_JOB_STORE", "./cache/platform/jobs.json")),
            max_workers=int(os.environ.get("PLATFORM_JOB_MAX_WORKERS", "2")),
        )
        app.state.gateway_service = GatewayService()
        app.state.monitor_service = MonitorService()
        app.state.api_metrics = APIMetrics()

        if enable_cors:
            app.add_middleware(
                CORSMiddleware,
                allow_origins=_resolve_allowed_origins(allowed_origins),
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )

        # Request ID middleware
        @app.middleware("http")
        async def add_request_id(request: Request, call_next):
            import uuid
            request_id = str(uuid.uuid4())[:8]
            request.state.request_id = request_id
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response

        @app.middleware("http")
        async def record_metrics(request: Request, call_next):
            response = await call_next(request)
            request.app.state.api_metrics.record(request.method, response.status_code)
            return response

        # Security headers
        @app.middleware("http")
        async def security_headers(request: Request, call_next):
            response = await call_next(request)
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            if request.url.scheme == "https":
                response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            return response

        # ---- Health endpoints ----

        @app.get("/api/v2/health", response_model=HealthResponse, tags=["Operations"])
        async def health():
            return HealthResponse(uptime_seconds=round(time.time() - _start_time, 3))

        @app.get("/api/v2/ready", tags=["Operations"])
        async def readiness():
            return {"ready": True}

        @app.get("/api/v2/metrics", tags=["Operations"])
        async def metrics(request: Request):
            return ApiEnvelope(data=request.app.state.api_metrics.snapshot(request.app.state.job_queue))

        @app.get("/health", include_in_schema=False)
        async def legacy_health():
            return await health()

        @app.get("/ready", include_in_schema=False)
        async def legacy_ready():
            return await readiness()

        @app.get("/metrics", include_in_schema=False)
        async def legacy_metrics(request: Request):
            return await metrics(request)

        # ---- Strategy endpoints ----

        @app.get("/api/v2/strategies", tags=["Strategies"])
        async def list_strategies():
            from src.backtest.strategy_modules import STRATEGY_REGISTRY
            items = []
            for name, module in sorted(STRATEGY_REGISTRY.items()):
                params = {}
                try:
                    defaults = module.coerce({})
                    params = {k: {"type": type(v).__name__, "default": v} for k, v in defaults.items()}
                except Exception:
                    pass
                items.append({"name": name, "description": getattr(module, "description", ""), "params": params})
            return ApiEnvelope(data={"count": len(items), "strategies": items})

        @app.get("/api/v2/strategies/{name}", tags=["Strategies"])
        async def get_strategy(name: str):
            from src.backtest.strategy_modules import STRATEGY_REGISTRY
            if name not in STRATEGY_REGISTRY:
                raise HTTPException(status_code=404, detail=f"Strategy '{name}' not found")
            module = STRATEGY_REGISTRY[name]
            params = {}
            try:
                defaults = module.coerce({})
                params = {k: {"type": type(v).__name__, "default": v} for k, v in defaults.items()}
            except Exception:
                pass
            return ApiEnvelope(data={"name": name, "description": getattr(module, "description", ""), "params": params})

        @app.post("/api/v2/strategies/validate", tags=["Strategies"])
        async def validate_strategy(req: StrategyValidateRequest):
            import ast
            errors = []
            try:
                tree = ast.parse(req.code)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name in ("os", "subprocess", "shutil", "sys"):
                                errors.append({"line": node.lineno, "message": f"Import '{alias.name}' restricted", "severity": "warning"})
                    elif isinstance(node, ast.ImportFrom):
                        if node.module and node.module.split(".")[0] in ("os", "subprocess", "shutil"):
                            errors.append({"line": node.lineno, "message": f"Import from '{node.module}' restricted", "severity": "warning"})
            except SyntaxError as e:
                errors.append({"line": e.lineno or 1, "message": str(e.msg), "severity": "error"})
            valid = not any(e["severity"] == "error" for e in errors)
            return ApiEnvelope(data={"valid": valid, "errors": errors})

        async def _run_backtest_impl(req: BacktestRequest):
            try:
                from src.backtest.engine import BacktestEngine
                engine = BacktestEngine()
                result = engine.run_strategy(
                    strategy=req.strategy,
                    symbols=req.symbols,
                    start=req.start,
                    end=req.end,
                    params=req.params,
                    cash=req.cash,
                    commission=req.commission,
                    slippage=req.slippage,
                )
                clean = {k: v for k, v in result.items() if k not in ("nav", "_cerebro", "_quality_report", "_data_fingerprint")}
                for k, v in clean.items():
                    if hasattr(v, "item"):
                        clean[k] = v.item()
                return ApiEnvelope(data={"metrics": clean})
            except KeyError as e:
                raise HTTPException(status_code=404, detail=str(e))
            except Exception as e:
                logger.error("backtest_failed", error=str(e))
                raise HTTPException(status_code=500, detail=str(e))

        @app.post("/api/v2/backtest/run", tags=["Backtest"])
        async def run_backtest(req: BacktestRequest):
            return await _run_backtest_impl(req)

        @app.post("/api/v2/strategies/run", tags=["Strategies"])
        async def run_strategy(req: BacktestRequest):
            return await _run_backtest_impl(req)

        @app.get("/api/v2/gateway/status", tags=["Trading"])
        async def gateway_status(request: Request):
            return ApiEnvelope(data={"gateway": request.app.state.gateway_service.status()})

        @app.post("/api/v2/gateway/connect", tags=["Trading"])
        async def gateway_connect(request: Request, payload: ConnectRequest):
            try:
                status = request.app.state.gateway_service.connect(payload.model_dump())
                return ApiEnvelope(data={"gateway": status})
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))

        @app.post("/api/v2/gateway/disconnect", tags=["Trading"])
        async def gateway_disconnect(request: Request):
            return ApiEnvelope(data={"gateway": request.app.state.gateway_service.disconnect()})

        @app.get("/api/v2/gateway/account", tags=["Trading"])
        async def gateway_account(request: Request):
            try:
                return ApiEnvelope(data={"account": request.app.state.gateway_service.account()})
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))

        @app.get("/api/v2/gateway/positions", tags=["Trading"])
        async def gateway_positions(request: Request):
            try:
                return ApiEnvelope(data={"positions": request.app.state.gateway_service.positions_list()})
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))

        @app.get("/api/v2/gateway/orders", tags=["Trading"])
        async def gateway_orders(request: Request, symbol: Optional[str] = None):
            try:
                return ApiEnvelope(data={"orders": request.app.state.gateway_service.orders(symbol=symbol)})
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))

        @app.get("/api/v2/gateway/trades", tags=["Trading"])
        async def gateway_trades(request: Request, symbol: Optional[str] = None, limit: int = 20):
            try:
                return ApiEnvelope(data={"trades": request.app.state.gateway_service.trades(symbol=symbol, limit=limit)})
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))

        @app.get("/api/v2/gateway/snapshot", tags=["Trading"])
        async def gateway_snapshot(request: Request, limit: int = 20):
            try:
                return ApiEnvelope(
                    data={
                        "gateway": request.app.state.gateway_service.snapshot(
                            orders_limit=limit,
                            trades_limit=limit,
                        )
                    }
                )
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))

        @app.post("/api/v2/gateway/order", tags=["Trading"])
        async def gateway_order(request: Request, payload: OrderRequest):
            try:
                result = request.app.state.gateway_service.submit_order(payload.model_dump())
                return ApiEnvelope(data=result)
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))

        @app.post("/api/v2/gateway/cancel", tags=["Trading"])
        async def gateway_cancel(request: Request, payload: CancelRequest):
            try:
                result = request.app.state.gateway_service.cancel_order(payload.model_dump())
                return ApiEnvelope(data=result)
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))

        @app.post("/api/v2/gateway/price", tags=["Trading"])
        async def gateway_price(request: Request, payload: PriceUpdateRequest):
            try:
                result = request.app.state.gateway_service.update_price(payload.model_dump())
                return ApiEnvelope(data=result)
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))

        @app.get("/api/v2/monitor/summary", tags=["Monitoring"])
        async def monitor_summary(request: Request, limit: int = 20):
            data = request.app.state.monitor_service.summary(
                queue=request.app.state.job_queue,
                gateway_service=request.app.state.gateway_service,
                metrics=request.app.state.api_metrics,
                jobs_limit=min(limit, 50),
                orders_limit=limit,
                trades_limit=limit,
            )
            return ApiEnvelope(data={"monitor": data})

        @app.get("/api/v2/monitor/history", tags=["Monitoring"])
        async def monitor_history(request: Request, limit: int = 20):
            return ApiEnvelope(data={"history": request.app.state.monitor_service.history(limit=limit)})

        @app.get("/api/v2/monitor/alerts", tags=["Monitoring"])
        async def monitor_alerts(request: Request, limit: int = 20):
            return ApiEnvelope(data={"alerts": request.app.state.monitor_service.alerts(limit=limit)})

        frontend_dist = _resolve_frontend_dist()
        if frontend_dist is not None:
            frontend_index = frontend_dist / "index.html"

            def _frontend_path(full_path: str) -> Path:
                requested = (frontend_dist / full_path).resolve()
                if requested != frontend_dist and frontend_dist not in requested.parents:
                    raise HTTPException(status_code=404, detail="Not Found")
                return requested

            @app.get("/", include_in_schema=False)
            async def serve_frontend_index():
                return FileResponse(frontend_index)

            @app.get("/{full_path:path}", include_in_schema=False)
            async def serve_frontend_asset(full_path: str):
                if full_path.startswith("api/"):
                    raise HTTPException(status_code=404, detail="Not Found")
                requested = _frontend_path(full_path)
                if requested.is_file():
                    return FileResponse(requested)
                return FileResponse(frontend_index)

        return app

    # Singleton app instance
    app = create_app()

else:
    # Stub when FastAPI is not installed
    app = None

    class ApiEnvelope:
        pass

    class HealthResponse:
        pass

    class BacktestRequest:
        pass

    class StrategyValidateRequest:
        pass

    class OrderRequest:
        pass

    class ConnectRequest:
        pass

    def create_app(**kwargs):
        raise ImportError("FastAPI is required: pip install fastapi uvicorn")
