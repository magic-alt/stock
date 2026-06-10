"""
FastAPI-based API server v2 (V5.0-C-1).

Provides async REST + WebSocket endpoints alongside the legacy ThreadingHTTPServer.
Features: auto OpenAPI docs, Pydantic validation, OAuth2 support, async handlers.
"""
from __future__ import annotations

import os
import time
import math
import uuid
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, timedelta
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.account_manager import AccountManager
from src.backtest.admission_gates import DEFAULT_STRATEGY_GATE_ROOT, MissingStrategyGateStage, require_strategy_stage
from src.core.capital_allocator import CapitalAllocator
from src.core.contracts import CONTRACT_VERSION
from src.core.logger import get_logger
from src.core.monitoring import TraceContext, get_metric_collector, get_tracer
from src.platform.runtime import BacktestRuntime, LiveRuntime, SandboxRuntime
from src.platform.api_server import APIMetrics, GatewayService, MonitorService
from src.platform.job_queue import JobQueue, JobStore

logger = get_logger("platform.api_v2")

try:
    from fastapi import FastAPI, HTTPException, Depends, Request, Response  # noqa: F401
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse, JSONResponse  # noqa: F401
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
        source: str = Field("auto", description="Market data provider")
        benchmark_source: Optional[str] = Field(None, description="Benchmark data provider")
        benchmark: Optional[str] = Field(None, description="Benchmark symbol")
        adj: Optional[str] = Field(None, description="Adjustment mode passed to the data provider")
        calendar_mode: Optional[str] = Field(None, description="Trading calendar alignment mode")
        engine: str = Field("backtrader", description="Execution backend name")

    class BacktestJobRequest(BacktestRequest):
        plot: bool = Field(False, description="Generate plot/report artifacts")
        report_dir: Optional[str] = Field(None, description="Optional report output directory")
        out_dir: Optional[str] = Field(None, description="Optional engine output directory")
        cache_dir: Optional[str] = Field(None, description="Optional provider cache directory")
        register_data_lake: bool = Field(True, description="Register report artifacts in the data lake")
        data_lake_dir: Optional[str] = Field(None, description="Optional data lake directory")

    class AnalysisRequest(BaseModel):
        symbol: str = Field("600519.SH", min_length=1, description="Stock symbol to analyze")
        days: int = Field(120, ge=10, le=500, description="Number of recent daily bars to inspect")
        source: str = Field(
            "auto",
            description="Data source: auto, akshare, sina, tencent, eastmoney, yfinance, tushare",
        )
        strategy: str = Field("macd", description="Lightweight preview strategy: macd or sma")
        include_backtest: bool = Field(True, description="Include a lightweight backtest preview")
        use_ai: bool = Field(False, description="Optionally request an OpenAI-compatible summary")

    class LocalDataUpdateRequest(BaseModel):
        symbol: str = Field("600519.SH", min_length=1, description="Stock symbol to update")
        source: str = Field("auto", description="Remote source used to refresh local DuckDB data")
        days: int = Field(250, ge=10, le=5000, description="Recent daily bars to fetch when start/end are omitted")
        start: Optional[str] = Field(None, description="Optional start date YYYY-MM-DD")
        end: Optional[str] = Field(None, description="Optional end date YYYY-MM-DD")
        freq: str = Field("daily", description="Local frequency label")
        adj: Optional[str] = Field(None, description="Adjustment mode passed to the data provider")
        replace: bool = Field(True, description="Replace existing local rows for symbol+freq")

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
        max_position_pct: float = 0.3
        max_order_value: float = 100000.0
        risk_config: Dict[str, Any] = Field(default_factory=dict)
        terminal_type: str = "QMT"
        terminal_path: str = ""
        trade_server: str = ""
        quote_server: str = ""
        client_id: int = 1
        td_front: str = ""
        md_front: str = ""
        sdk_path: str = ""
        sdk_log_path: str = ""
        gateway_provider: str = "self"
        qmt_provider: str = "self"
        vnpy_gateway: str = ""
        vnpy_setting: Dict[str, Any] = Field(default_factory=dict)
        broker_options: Dict[str, Any] = Field(default_factory=dict)

    class CancelRequest(BaseModel):
        order_id: str = Field(..., min_length=1)

    class PriceUpdateRequest(BaseModel):
        symbol: str = Field(..., min_length=1)
        price: float = Field(..., gt=0)

    class AccountCreateRequest(BaseModel):
        account_group: str = Field("default", min_length=1)
        owner_id: str = Field("api", min_length=1)
        initial_cash: float = Field(0.0, ge=0)
        metadata: Dict[str, Any] = Field(default_factory=dict)

    class FundTransferRequest(BaseModel):
        from_account_id: str = Field(..., min_length=1)
        to_account_id: str = Field(..., min_length=1)
        amount: float = Field(..., gt=0)

    class CapitalAllocationPreviewRequest(BaseModel):
        account_group: str = Field("default", min_length=1)
        strategy_weights: Dict[str, float] = Field(..., min_length=1)
        strategy_params: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
        gate_root: str = Field(DEFAULT_STRATEGY_GATE_ROOT, min_length=1)
        total_capital: Optional[float] = Field(None, gt=0)
        min_cash_buffer_pct: float = Field(0.05, ge=0, lt=1)
        max_account_weight: float = Field(1.0, gt=0, le=1)
        max_strategy_weight: float = Field(0.5, gt=0, le=1)

    def _jsonable(value: Any) -> Any:
        if is_dataclass(value):
            return {k: _jsonable(v) for k, v in asdict(value).items()}
        if isinstance(value, dict):
            return {k: _jsonable(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [_jsonable(v) for v in value]
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return None
        if hasattr(value, "item"):
            try:
                return _jsonable(value.item())
            except Exception:
                return value
        return value

    def _model_dump(model: BaseModel, **kwargs: Any) -> Dict[str, Any]:
        return model.model_dump(**kwargs)

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
        return ["http://localhost:3000", "http://127.0.0.1:3000"]

    def _resolve_frontend_dist() -> Optional[Path]:
        raw_path = os.environ.get("PLATFORM_FRONTEND_DIST", "").strip()
        frontend_dist = Path(raw_path) if raw_path else PROJECT_ROOT / "frontend" / "dist"
        index_file = frontend_dist / "index.html"
        if frontend_dist.is_dir() and index_file.is_file():
            return frontend_dist.resolve()
        return None

    def _resolve_market_data_duckdb_path() -> str:
        from src.core.config import get_config

        db_path = os.environ.get("MARKET_DATA_DUCKDB_PATH", "").strip()
        if not db_path:
            db_path = get_config().config.database.duckdb_path
        return db_path

    def _open_local_market_data_store(db_path: Optional[str] = None):
        from src.data_sources.duckdb_store import DuckDBConfig, DuckDBTimeSeriesStore

        resolved_path = db_path or _resolve_market_data_duckdb_path()
        if resolved_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(resolved_path)) or ".", exist_ok=True)
        return DuckDBTimeSeriesStore(DuckDBConfig(db_path=resolved_path))

    def _initialize_local_market_data_store(app: FastAPI) -> None:
        app.state.local_market_data_initialized = False
        app.state.local_market_data_error = ""
        try:
            store = _open_local_market_data_store(app.state.local_market_data_db_path)
            try:
                stats = store.stats()
            finally:
                store.close()
            app.state.local_market_data_initialized = True
            logger.info(
                "local_market_data_store_initialized",
                db_path=app.state.local_market_data_db_path,
                rows=stats.get("total_rows", 0),
            )
        except ImportError as exc:
            app.state.local_market_data_error = str(exc)
            logger.warning("local_market_data_store_unavailable", error=str(exc))
        except Exception as exc:
            app.state.local_market_data_error = str(exc)
            logger.warning("local_market_data_store_init_failed", error=str(exc))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("fastapi_starting")
        _initialize_local_market_data_store(app)
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
        app.state.metric_collector = get_metric_collector()
        app.state.tracer = get_tracer()
        app.state.account_manager = AccountManager()
        app.state.capital_allocator = CapitalAllocator()
        app.state.local_market_data_db_path = _resolve_market_data_duckdb_path()
        app.state.local_market_data_initialized = False
        app.state.local_market_data_error = ""
        app.state.runtime_contexts = {
            "backtest": BacktestRuntime(metrics=app.state.metric_collector, tracer=app.state.tracer),
            "sandbox": SandboxRuntime(metrics=app.state.metric_collector, tracer=app.state.tracer),
            "live": LiveRuntime(metrics=app.state.metric_collector, tracer=app.state.tracer),
        }

        if enable_cors:
            app.add_middleware(
                CORSMiddleware,
                allow_origins=_resolve_allowed_origins(allowed_origins),
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )

        # Request/trace context middleware
        @app.middleware("http")
        async def add_request_context(request: Request, call_next):
            request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:8]
            trace_id = request.headers.get("X-Trace-ID") or request_id
            parent_span_id = request.headers.get("X-Span-ID") or ""
            request.state.request_id = request_id
            request.state.trace_id = trace_id
            request.state.trace_context = TraceContext(trace_id=trace_id, span_id=parent_span_id)
            started_at = time.time()
            with request.app.state.tracer.trace(
                f"{request.method} {request.url.path}",
                trace_context=request.state.trace_context,
            ) as span:
                span.set_attribute("http.method", request.method)
                span.set_attribute("http.path", request.url.path)
                span.set_attribute("request_id", request_id)
                response = await call_next(request)
                duration_ms = (time.time() - started_at) * 1000.0
                span.set_attribute("http.status_code", response.status_code)
                request.app.state.metric_collector.counter("platform_api_requests", 1)
                request.app.state.metric_collector.counter(f"platform_api_status_{response.status_code}", 1)
                request.app.state.metric_collector.histogram("platform_api_request_duration_ms", duration_ms)
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Trace-ID"] = trace_id
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

        @app.get("/api/v2/info", tags=["Operations"])
        async def info(request: Request):
            return ApiEnvelope(
                data={
                    "name": "Unified Quant Platform",
                    "version": app.version,
                    "contract_version": CONTRACT_VERSION,
                    "runtimes": {
                        name: runtime.info()
                        for name, runtime in request.app.state.runtime_contexts.items()
                    },
                }
            )

        @app.get("/api/v2/metrics", tags=["Operations"])
        async def metrics(request: Request, format: str = "json"):
            if format.lower() in {"prometheus", "prom"}:
                body = request.app.state.api_metrics.to_prometheus(request.app.state.job_queue)
                body += request.app.state.metric_collector.to_prometheus()
                return Response(content=body, media_type="text/plain; version=0.0.4")
            return ApiEnvelope(data=request.app.state.api_metrics.snapshot(request.app.state.job_queue))

        def _local_market_data_store():
            return _open_local_market_data_store(app.state.local_market_data_db_path)

        def _chart_payload_from_frame(
            *,
            symbol: str,
            source: str,
            df,
            data_quality: Optional[Dict[str, Any]] = None,
        ) -> Dict[str, Any]:
            dates = [str(d.date()) if hasattr(d, "date") else str(d) for d in df.index]
            ohlc = [
                [float(row["open"]), float(row["close"]), float(row["low"]), float(row["high"])]
                for _, row in df.iterrows()
            ]
            volumes = [float(row.get("volume", 0)) for _, row in df.iterrows()]
            quality = data_quality or {
                "source": source,
                "rows": len(df),
                "warnings": [],
                "validation_status": "local" if source == "local" else "loaded",
            }
            return {
                "symbol": symbol,
                "source": quality.get("source", source),
                "dates": dates,
                "ohlc": ohlc,
                "volumes": volumes,
                "warnings": quality.get("warnings", []),
                "data_quality": quality,
            }

        @app.get("/api/v2/local-data", tags=["Data"])
        async def list_local_data(freq: str = "daily"):
            try:
                store = _local_market_data_store()
                try:
                    datasets = store.list_datasets(freq=freq.strip() or None)
                    stats = store.stats()
                finally:
                    store.close()
                return ApiEnvelope(
                    data={
                        "datasets": datasets,
                        "stats": stats,
                        "db_path": stats.get("db_path", app.state.local_market_data_db_path),
                        "initialized": bool(app.state.local_market_data_initialized),
                    }
                )
            except ImportError as exc:
                raise HTTPException(status_code=503, detail=str(exc))
            except Exception as exc:
                logger.error("local_data_list_failed", error=str(exc))
                raise HTTPException(status_code=500, detail=str(exc))

        @app.post("/api/v2/local-data/update", tags=["Data"])
        async def update_local_data(req: LocalDataUpdateRequest):
            from src.data_sources.providers import normalize_a_share_symbol
            from src.platform.analysis_service import StockAnalysisService

            symbol = normalize_a_share_symbol(req.symbol)
            if not symbol.strip():
                raise HTTPException(status_code=400, detail="symbol is required")
            source = req.source.strip().lower() or "auto"
            if source == "local":
                raise HTTPException(status_code=400, detail="source=local cannot refresh local data")
            freq = req.freq.strip().lower() or "daily"
            end = req.end or date.today().isoformat()
            start = req.start or (datetime.strptime(end, "%Y-%m-%d").date() - timedelta(days=req.days * 2)).isoformat()
            try:
                service = StockAnalysisService()
                df, data_quality = service.load_history_range(
                    symbol=symbol,
                    start=start,
                    end=end,
                    source=source,
                )
                if not req.start and not req.end:
                    df = df.tail(req.days)

                if df is None or df.empty:
                    raise HTTPException(status_code=404, detail=f"no OHLCV data found for {symbol}")

                store = _local_market_data_store()
                try:
                    rows = store.ingest(symbol, df, freq=freq, replace=req.replace)
                    datasets = [item for item in store.list_datasets(freq=freq) if item["symbol"] == symbol]
                    stats = store.stats()
                finally:
                    store.close()
                return ApiEnvelope(
                    data={
                        "symbol": symbol,
                        "source": data_quality.get("source", source),
                        "rows": rows,
                        "dataset": datasets[0] if datasets else None,
                        "stats": stats,
                        "data_quality": {**data_quality, "rows": rows},
                    }
                )
            except HTTPException:
                raise
            except ImportError as exc:
                raise HTTPException(status_code=503, detail=str(exc))
            except Exception as exc:
                logger.error("local_data_update_failed", error=str(exc))
                raise HTTPException(status_code=500, detail=str(exc))

        @app.get("/api/v2/chart-data", tags=["Data"])
        async def chart_data(symbol: str, days: int = 120, source: str = "auto"):
            from src.data_sources.providers import normalize_a_share_symbol
            from src.platform.analysis_service import StockAnalysisService

            normalized_symbol = normalize_a_share_symbol(symbol)
            if not normalized_symbol.strip():
                raise HTTPException(status_code=400, detail="symbol is required")
            days = max(10, min(days, 5000))
            try:
                provider_source = source.strip().lower() or "auto"
                if provider_source == "local":
                    store = _local_market_data_store()
                    try:
                        df = store.query(normalized_symbol, freq="daily").tail(days)
                        local_rows = store.count(normalized_symbol, freq="daily")
                    finally:
                        store.close()
                    data_quality = {
                        "source": "local",
                        "rows": int(local_rows),
                        "warnings": [],
                        "validation_status": "local_duckdb",
                    }
                else:
                    service = StockAnalysisService()
                    df, data_quality = service._load_history(
                        symbol=normalized_symbol,
                        days=days,
                        source=provider_source,
                    )

                if df is None or df.empty:
                    raise HTTPException(
                        status_code=404,
                        detail=(
                            f"no OHLCV data found for {normalized_symbol}; attempted: "
                            f"{', '.join(data_quality.get('attempted_sources', [provider_source]))}"
                        ),
                    )

                df = df.tail(days)
                return ApiEnvelope(data=_chart_payload_from_frame(
                    symbol=normalized_symbol,
                    source=provider_source,
                    df=df,
                    data_quality=data_quality,
                ))
            except HTTPException:
                raise
            except ImportError as exc:
                raise HTTPException(status_code=503, detail=str(exc))
            except Exception as e:
                logger.error("chart_data_failed", error=str(e))
                raise HTTPException(status_code=500, detail=str(e))

        # ---- Beginner analysis endpoints ----

        @app.get("/api/v2/analysis/capabilities", tags=["Analysis"])
        async def analysis_capabilities():
            from src.platform.analysis_service import StockAnalysisService

            return ApiEnvelope(data=StockAnalysisService().capabilities())

        @app.post("/api/v2/analysis/run", tags=["Analysis"])
        async def run_analysis(req: AnalysisRequest):
            from src.platform.analysis_service import AnalysisRequestPayload, StockAnalysisService

            try:
                payload = AnalysisRequestPayload(**_model_dump(req))
                result = StockAnalysisService().analyze(payload)
                return ApiEnvelope(data={"analysis": result})
            except LookupError as exc:
                raise HTTPException(status_code=404, detail=str(exc))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            except Exception as exc:
                logger.error("analysis_failed", error=str(exc))
                raise HTTPException(status_code=500, detail=str(exc))

        @app.post("/api/v2/analysis/jobs", tags=["Analysis"])
        async def submit_analysis_job(request: Request, req: AnalysisRequest):
            from src.platform.analysis_service import run_stock_analysis_task

            payload = _model_dump(req)
            idempotency_key = request.headers.get("X-Idempotency-Key") or None
            job_id = request.app.state.job_queue.submit(
                "analysis",
                run_stock_analysis_task,
                payload,
                idempotency_key=idempotency_key,
            )
            return ApiEnvelope(data={"job_id": job_id})

        @app.get("/api/v2/analysis/jobs", tags=["Analysis"])
        async def list_analysis_jobs(request: Request, limit: int = 20):
            jobs = [
                _jsonable(job)
                for job in sorted(
                    request.app.state.job_queue.store.list(),
                    key=lambda item: item.created_at,
                    reverse=True,
                )
                if job.task_type == "analysis"
            ]
            return ApiEnvelope(data={"jobs": jobs[: max(0, min(limit, 100))]})

        @app.get("/api/v2/analysis/jobs/{job_id}", tags=["Analysis"])
        async def get_analysis_job(request: Request, job_id: str):
            record = request.app.state.job_queue.store.get(job_id)
            if record is None or record.task_type != "analysis":
                raise HTTPException(status_code=404, detail="job not found")
            return ApiEnvelope(data={"job": _jsonable(record)})

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

        def _build_fallback_technical_chart(req: BacktestRequest) -> Dict[str, Any]:
            from src.data_sources.providers import normalize_a_share_symbol
            from src.platform.backtest_charts import build_technical_chart_payload_from_frame

            symbol = normalize_a_share_symbol(req.symbols[0])
            try:
                from src.data_sources.providers import get_provider

                if req.source == "auto":
                    from src.platform.verified_history_gateway import VerifiedHistoryGateway

                    gateway = VerifiedHistoryGateway(source="auto", benchmark_source=req.benchmark_source)
                    data_map = gateway.load_bars([symbol], req.start, req.end, adj=req.adj)
                else:
                    provider = get_provider(req.source)
                    data_map = provider.load_stock_daily([symbol], req.start, req.end, adj=req.adj)
                payload = build_technical_chart_payload_from_frame(data_map.get(symbol), symbol=symbol)
                if payload.get("technical_chart"):
                    return payload
            except Exception as exc:
                logger.warning("backtest_chart_fallback_failed", error=str(exc))
            return {"technical_chart": None}

        def _is_market_data_error(exc: Exception) -> bool:
            message = str(exc).lower()
            markers = (
                "no data",
                "not available",
                "remote end closed",
                "connection",
                "could not resolve",
                "name or service",
                "nodename nor servname",
                "failed to establish",
                "market data",
            )
            return any(marker in message for marker in markers)

        async def _run_backtest_impl(req: BacktestRequest):
            try:
                from src.backtest.engine import BacktestEngine
                from src.platform.backtest_charts import build_nav_chart_payload, build_technical_chart_payload

                from src.data_sources.providers import normalize_a_share_symbol

                normalized_symbols = [normalize_a_share_symbol(item) for item in req.symbols]
                use_verified_auto = req.source == "auto"
                engine_source = "sina" if use_verified_auto else req.source
                engine_benchmark_source = req.benchmark_source or engine_source
                if engine_benchmark_source == "auto":
                    engine_benchmark_source = engine_source
                engine_req = req.model_copy(
                    update={
                        "symbols": normalized_symbols,
                        "source": engine_source,
                        "benchmark_source": engine_benchmark_source,
                    }
                )
                engine_name = req.engine or "backtrader"
                capture_cerebro = engine_name.lower() in ("backtrader", "bt")
                history_gateway = None
                if use_verified_auto:
                    from src.platform.verified_history_gateway import VerifiedHistoryGateway

                    history_gateway = VerifiedHistoryGateway(
                        source="auto",
                        benchmark_source=req.benchmark_source or "auto",
                    )
                engine = BacktestEngine(
                    source=engine_req.source,
                    benchmark_source=engine_req.benchmark_source or engine_req.source,
                    calendar_mode=engine_req.calendar_mode or "off",
                    history_gateway=history_gateway,
                )
                result = engine.run_strategy(
                    strategy=engine_req.strategy,
                    symbols=engine_req.symbols,
                    start=engine_req.start,
                    end=engine_req.end,
                    params=engine_req.params,
                    cash=engine_req.cash,
                    commission=engine_req.commission,
                    slippage=engine_req.slippage,
                    benchmark=engine_req.benchmark,
                    adj=engine_req.adj,
                    calendar_mode=engine_req.calendar_mode,
                    enable_plot=capture_cerebro,
                    engine=engine_name,
                )
                if result.get("error") and _is_market_data_error(Exception(str(result.get("error")))):
                    raise HTTPException(status_code=404, detail=str(result.get("error")))
                chart_payload = build_nav_chart_payload(result.get("nav"))
                technical_payload = build_technical_chart_payload(result.get("_cerebro"))
                if not technical_payload.get("technical_chart"):
                    technical_payload = _build_fallback_technical_chart(engine_req)
                chart_payload.update(technical_payload)
                clean = {
                    k: _jsonable(v)
                    for k, v in result.items()
                    if k not in ("nav", "_cerebro", "_quality_report", "_data_fingerprint")
                }
                clean.update(chart_payload)
                return ApiEnvelope(data={"metrics": clean})
            except KeyError as e:
                raise HTTPException(status_code=404, detail=str(e))
            except HTTPException:
                raise
            except Exception as e:
                if _is_market_data_error(e):
                    raise HTTPException(status_code=404, detail=f"real market data unavailable: {e}")
                logger.error("backtest_failed", error=str(e))
                raise HTTPException(status_code=500, detail=str(e))

        @app.post("/api/v2/backtest/run", tags=["Backtest"])
        async def run_backtest(req: BacktestRequest):
            return await _run_backtest_impl(req)

        @app.post("/api/v2/strategies/run", tags=["Strategies"])
        async def run_strategy(req: BacktestRequest):
            return await _run_backtest_impl(req)

        @app.post("/api/v2/backtest/jobs", tags=["Backtest"])
        async def submit_backtest_job(request: Request, req: BacktestJobRequest):
            from src.platform.backtest_task import run_backtest_job

            payload = _model_dump(req, exclude_none=True)
            idempotency_key = request.headers.get("X-Idempotency-Key") or None
            job_id = request.app.state.job_queue.submit(
                "backtest",
                run_backtest_job,
                payload,
                idempotency_key=idempotency_key,
            )
            return ApiEnvelope(data={"job_id": job_id})

        @app.get("/api/v2/backtest/jobs", tags=["Backtest"])
        async def list_backtest_jobs(request: Request, limit: int = 20):
            jobs = [
                _jsonable(job)
                for job in sorted(
                    request.app.state.job_queue.store.list(),
                    key=lambda item: item.created_at,
                    reverse=True,
                )
                if job.task_type == "backtest"
            ]
            return ApiEnvelope(data={"jobs": jobs[: max(0, min(limit, 100))]})

        @app.get("/api/v2/backtest/jobs/{job_id}", tags=["Backtest"])
        async def get_backtest_job(request: Request, job_id: str):
            record = request.app.state.job_queue.store.get(job_id)
            if record is None or record.task_type != "backtest":
                raise HTTPException(status_code=404, detail="job not found")
            return ApiEnvelope(data={"job": _jsonable(record)})

        @app.post("/api/v2/backtest/jobs/{job_id}/cancel", tags=["Backtest"])
        async def cancel_backtest_job(request: Request, job_id: str):
            existing = request.app.state.job_queue.store.get(job_id)
            if existing is None or existing.task_type != "backtest":
                raise HTTPException(status_code=404, detail="job not found")
            try:
                record = request.app.state.job_queue.cancel(job_id)
            except KeyError:
                raise HTTPException(status_code=404, detail="job not found")
            except RuntimeError as exc:
                raise HTTPException(status_code=409, detail=str(exc))
            return ApiEnvelope(data={"job": _jsonable(record)})

        @app.get("/api/v2/gateway/status", tags=["Trading"])
        async def gateway_status(request: Request):
            return ApiEnvelope(data={"gateway": request.app.state.gateway_service.status()})

        @app.post("/api/v2/gateway/connect", tags=["Trading"])
        async def gateway_connect(request: Request, payload: ConnectRequest):
            try:
                status = request.app.state.gateway_service.connect(payload.model_dump(exclude_unset=True))
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

        @app.post("/api/v2/accounts", tags=["Accounts"])
        async def create_account(request: Request, payload: AccountCreateRequest):
            account = request.app.state.account_manager.create_account(
                payload.account_group,
                payload.owner_id,
                payload.initial_cash,
            )
            account.metadata.update(payload.metadata)
            return ApiEnvelope(data={"account": _jsonable(account)})

        @app.get("/api/v2/accounts", tags=["Accounts"])
        async def list_accounts(request: Request, account_group: str = "default"):
            accounts = request.app.state.account_manager.list_accounts(account_group)
            return ApiEnvelope(data={"accounts": _jsonable(accounts)})

        @app.get("/api/v2/accounts/{account_id}/risk", tags=["Accounts"])
        async def account_risk(request: Request, account_id: str):
            try:
                summary = request.app.state.account_manager.get_account_risk_summary(account_id)
                return ApiEnvelope(data={"risk": summary})
            except KeyError as exc:
                raise HTTPException(status_code=404, detail=str(exc))

        @app.post("/api/v2/accounts/transfer", tags=["Accounts"])
        async def transfer_funds(request: Request, payload: FundTransferRequest):
            try:
                result = request.app.state.account_manager.fund_transfer(
                    payload.from_account_id,
                    payload.to_account_id,
                    payload.amount,
                )
                return ApiEnvelope(data={"transfer": result})
            except KeyError as exc:
                raise HTTPException(status_code=404, detail=str(exc))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))

        @app.post("/api/v2/portfolio/capital-allocation/preview", tags=["Portfolio"])
        async def preview_capital_allocation(request: Request, payload: CapitalAllocationPreviewRequest):
            for strategy_name in payload.strategy_weights:
                try:
                    require_strategy_stage(
                        strategy_name,
                        "admission_passed",
                        params=payload.strategy_params.get(strategy_name, {}),
                        gate_root=payload.gate_root,
                    )
                except MissingStrategyGateStage as exc:
                    raise HTTPException(status_code=403, detail=str(exc))

            accounts = request.app.state.account_manager.list_accounts(payload.account_group)
            allocator = CapitalAllocator(
                min_cash_buffer_pct=payload.min_cash_buffer_pct,
                max_account_weight=payload.max_account_weight,
                max_strategy_weight=payload.max_strategy_weight,
            )
            try:
                result = allocator.allocate(
                    accounts,
                    payload.strategy_weights,
                    total_capital=payload.total_capital,
                )
                return ApiEnvelope(data={"allocation": _jsonable(result)})
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))

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

        @app.get("/api/v2/demo/paper-trading", tags=["Demo"])
        async def demo_paper_trading(
            request: Request,
            symbol: str = "600519.SH",
            quantity: float = 100.0,
            limit: int = 20,
        ):
            from src.platform.demo import run_paper_trading_demo

            demo_gateway = GatewayService()
            demo = run_paper_trading_demo(
                demo_gateway,
                queue=request.app.state.job_queue,
                monitor_service=request.app.state.monitor_service,
                metrics=request.app.state.api_metrics,
                symbol=symbol,
                quantity=quantity,
                limit=max(1, min(limit, 50)),
            )
            return ApiEnvelope(data={"demo": demo})

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
