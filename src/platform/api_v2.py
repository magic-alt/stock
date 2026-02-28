"""
FastAPI-based API server v2 (V5.0-C-1).

Provides async REST + WebSocket endpoints alongside the legacy ThreadingHTTPServer.
Features: auto OpenAPI docs, Pydantic validation, OAuth2 support, async handlers.
"""
from __future__ import annotations

import time
import threading
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from src.core.logger import get_logger

logger = get_logger("platform.api_v2")

try:
    from fastapi import FastAPI, HTTPException, Depends, Request, Response
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, Field
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


# ---------------------------------------------------------------------------
# Pydantic models (request/response schemas)
# ---------------------------------------------------------------------------

if HAS_FASTAPI:

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
        price: float = Field(0, ge=0)
        order_type: str = Field("limit", pattern="^(market|limit)$")

    class ConnectRequest(BaseModel):
        mode: str = "paper"
        broker: str = "paper"
        initial_cash: float = 1000000

    # ------------------------------------------------------------------
    # Application factory
    # ------------------------------------------------------------------

    _start_time = time.time()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("fastapi_starting")
        yield
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

        if enable_cors:
            app.add_middleware(
                CORSMiddleware,
                allow_origins=allowed_origins or ["http://localhost:3000"],
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

        @app.post("/api/v2/backtest/run", tags=["Backtest"])
        async def run_backtest(req: BacktestRequest):
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
