"""
HTTP API server for platform job orchestration.

Provides:
- Legacy endpoints (/jobs, /gateway/*) for backward compatibility
- Versioned API endpoints (/api/v1/*) with unified response envelope
- Optional Bearer token authentication for v1 endpoints
- Health/readiness/metrics endpoints for operations
- Optional audit logging for key actions
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from collections import Counter
from dataclasses import asdict, is_dataclass
from enum import Enum
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from src.core.audit import AuditLogger, audit_event
from src.core.logger import get_logger
from src.core.trading_gateway import BrokerType, GatewayConfig, TradingGateway, TradingMode
from src.core.interfaces import OrderTypeEnum
from src.platform.backtest_task import run_backtest_job
from src.platform.job_queue import JobQueue, JobStore
from src.platform.orchestrator import run_workflow
from urllib.parse import parse_qs

WEB_ROOT = os.path.join(os.path.dirname(__file__), "web")
API_PREFIX = "/api/v1"

logger = get_logger("platform.api")


def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {k: _to_jsonable(v) for k, v in asdict(value).items()}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    return value


class APIMetrics:
    """Thread-safe in-memory metrics for lightweight operations visibility."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started_at = time.time()
        self._total_requests = 0
        self._status_counter: Counter[int] = Counter()
        self._method_counter: Counter[str] = Counter()

    def record(self, method: str, status_code: int) -> None:
        with self._lock:
            self._total_requests += 1
            self._status_counter[status_code] += 1
            self._method_counter[method] += 1

    def snapshot(self, queue: Optional[JobQueue] = None) -> Dict[str, Any]:
        with self._lock:
            payload = {
                "uptime_seconds": round(time.time() - self._started_at, 3),
                "total_requests": self._total_requests,
                "requests_by_status": {str(k): v for k, v in sorted(self._status_counter.items())},
                "requests_by_method": dict(sorted(self._method_counter.items())),
            }
        if queue is not None:
            payload["job_queue"] = queue.metrics()
        return payload

    def to_prometheus(self, queue: Optional[JobQueue] = None) -> str:
        snap = self.snapshot(queue)
        lines = [
            "# HELP platform_api_uptime_seconds Process uptime in seconds",
            "# TYPE platform_api_uptime_seconds gauge",
            f"platform_api_uptime_seconds {snap['uptime_seconds']}",
            "# HELP platform_api_requests_total Total HTTP requests handled",
            "# TYPE platform_api_requests_total counter",
            f"platform_api_requests_total {snap['total_requests']}",
        ]
        for method, count in sorted(snap.get("requests_by_method", {}).items()):
            lines.append(f'platform_api_requests_by_method_total{{method="{method}"}} {count}')
        for status, count in sorted(snap.get("requests_by_status", {}).items()):
            lines.append(f'platform_api_requests_by_status_total{{status="{status}"}} {count}')

        queue_metrics = snap.get("job_queue") or {}
        if queue_metrics:
            lines.extend(
                [
                    "# HELP platform_job_queue_jobs_total Total jobs observed",
                    "# TYPE platform_job_queue_jobs_total gauge",
                    f"platform_job_queue_jobs_total {queue_metrics.get('total_jobs', 0)}",
                    f"platform_job_queue_pending_jobs {queue_metrics.get('pending_jobs', 0)}",
                    f"platform_job_queue_running_jobs {queue_metrics.get('running_jobs', 0)}",
                    f"platform_job_queue_success_jobs {queue_metrics.get('success_jobs', 0)}",
                    f"platform_job_queue_failed_jobs {queue_metrics.get('failed_jobs', 0)}",
                    f"platform_job_queue_cancelled_jobs {queue_metrics.get('cancelled_jobs', 0)}",
                    f"platform_job_queue_in_flight_futures {queue_metrics.get('in_flight_futures', 0)}",
                    f"platform_job_queue_delay_ms_p50 {queue_metrics.get('queue_delay_ms_p50', 0.0)}",
                    f"platform_job_queue_delay_ms_p95 {queue_metrics.get('queue_delay_ms_p95', 0.0)}",
                    f"platform_job_queue_delay_ms_p99 {queue_metrics.get('queue_delay_ms_p99', 0.0)}",
                    f"platform_job_queue_run_ms_p50 {queue_metrics.get('run_duration_ms_p50', 0.0)}",
                    f"platform_job_queue_run_ms_p95 {queue_metrics.get('run_duration_ms_p95', 0.0)}",
                    f"platform_job_queue_run_ms_p99 {queue_metrics.get('run_duration_ms_p99', 0.0)}",
                ]
            )

        return "\n".join(lines) + "\n"


class GatewayService:
    """Thread-safe wrapper for a singleton trading gateway instance."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._gateway: Optional[TradingGateway] = None
        self._last_error: Optional[str] = None

    def connect(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        config = self._build_config(payload)
        gateway = TradingGateway(config)
        ok = gateway.connect()
        with self._lock:
            self._gateway = gateway
            self._last_error = None if ok else "connect_failed"
        return self.status()

    def disconnect(self) -> Dict[str, Any]:
        with self._lock:
            if not self._gateway:
                return {"status": "disconnected"}
            self._gateway.disconnect()
            return self.status()

    def status(self) -> Dict[str, Any]:
        with self._lock:
            if not self._gateway:
                return {"status": "disconnected"}
            return {
                "status": self._gateway.status.value,
                "connected": self._gateway.is_connected(),
                "mode": self._gateway.config.mode.value,
                "broker": self._gateway.config.broker.value,
                "last_error": self._last_error,
            }

    def account(self) -> Dict[str, Any]:
        gateway = self._require_gateway()
        return _to_jsonable(gateway.get_account())

    def positions(self) -> Dict[str, Any]:
        gateway = self._require_gateway()
        return _to_jsonable(gateway.get_positions())

    def submit_order(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        gateway = self._require_gateway()
        symbol = str(payload.get("symbol", "")).strip()
        side = str(payload.get("side", "buy")).lower()
        quantity = float(payload.get("quantity", 0))
        price_raw = payload.get("price")
        price = float(price_raw) if price_raw not in (None, "") else None
        order_type_raw = payload.get("order_type", OrderTypeEnum.LIMIT.value)
        order_type = OrderTypeEnum(order_type_raw)
        if side == "buy":
            order_id = gateway.buy(symbol, quantity, price=price, order_type=order_type)
        else:
            order_id = gateway.sell(symbol, quantity, price=price, order_type=order_type)
        return {"order_id": order_id}

    def cancel_order(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        gateway = self._require_gateway()
        order_id = str(payload.get("order_id", "")).strip()
        return {"cancelled": gateway.cancel(order_id)}

    def update_price(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        gateway = self._require_gateway()
        symbol = str(payload.get("symbol", "")).strip()
        price = float(payload.get("price", 0.0))
        gateway.update_price(symbol, price)
        return {"symbol": symbol, "price": price}

    def _require_gateway(self) -> TradingGateway:
        with self._lock:
            if not self._gateway:
                raise RuntimeError("gateway not connected")
            return self._gateway

    def _build_config(self, payload: Dict[str, Any]) -> GatewayConfig:
        mode = TradingMode(payload.get("mode", "paper"))
        broker = BrokerType(payload.get("broker", "paper"))
        return GatewayConfig(
            mode=mode,
            broker=broker,
            host=str(payload.get("host", "")),
            port=int(payload.get("port", 0) or 0),
            api_key=str(payload.get("api_key", "")),
            secret=str(payload.get("secret", "")),
            account=str(payload.get("account", "")),
            password=str(payload.get("password", "")),
            initial_cash=float(payload.get("initial_cash", 1_000_000.0)),
            commission_rate=float(payload.get("commission_rate", 0.0003)),
            slippage=float(payload.get("slippage", 0.0001)),
            enable_risk_check=bool(payload.get("enable_risk_check", True)),
            terminal_type=str(payload.get("terminal_type", "QMT")),
            terminal_path=str(payload.get("terminal_path", "")),
            trade_server=str(payload.get("trade_server", "")),
            quote_server=str(payload.get("quote_server", "")),
            client_id=int(payload.get("client_id", 1) or 1),
            td_front=str(payload.get("td_front", "")),
            md_front=str(payload.get("md_front", "")),
            broker_options=dict(payload.get("broker_options", {}) or {}),
        )


class PlatformAPIHandler(BaseHTTPRequestHandler):
    queue: JobQueue
    gateway_service: GatewayService
    metrics: APIMetrics
    api_token: Optional[str]
    audit_logger: Optional[AuditLogger]

    def _request_id(self) -> str:
        rid = self.headers.get("X-Request-ID", "").strip()
        return rid if rid else str(uuid.uuid4())

    def _actor(self) -> str:
        actor = self.headers.get("X-Actor", "").strip()
        return actor or "api"

    def _idempotency_key(self, payload: Optional[Dict[str, Any]] = None) -> Optional[str]:
        header_key = self.headers.get("X-Idempotency-Key", "").strip()
        if header_key:
            return header_key
        if payload and payload.get("idempotency_key"):
            return str(payload.get("idempotency_key")).strip()
        return None

    def _audit(
        self,
        *,
        action: str,
        resource: str,
        result: str,
        request_id: Optional[str],
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        audit_event(
            getattr(self, "audit_logger", None),
            actor=self._actor(),
            action=action,
            resource=resource,
            result=result,
            details={
                "request_id": request_id,
                "method": self.command,
                "path": self.path,
                **(details or {}),
            },
        )

    def _log_response(self, status: int) -> None:
        started = getattr(self, "_request_started_at", None)
        duration_ms = 0.0
        if isinstance(started, (float, int)):
            duration_ms = (time.time() - float(started)) * 1000.0
        logger.info(
            "api.response",
            method=self.command,
            path=self.path,
            status=status,
            request_id=getattr(self, "_current_request_id", ""),
            duration_ms=round(duration_ms, 3),
        )

    def _json(
        self,
        payload: Any,
        *,
        status: int = 200,
        content_type: str = "application/json; charset=utf-8",
    ) -> None:
        if content_type.startswith("application/json"):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        else:
            body = str(payload).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

        if getattr(self, "metrics", None) is not None:
            self.metrics.record(self.command, status)
        self._log_response(status)

    def _json_v1(
        self,
        *,
        request_id: str,
        data: Any = None,
        status: int = 200,
        code: int = 0,
        message: str = "ok",
    ) -> None:
        self._json(
            {
                "code": code,
                "message": message,
                "data": _to_jsonable(data),
                "request_id": request_id,
            },
            status=status,
        )

    def _error_v1(self, *, request_id: str, status: int, code: int, message: str) -> None:
        self._json_v1(request_id=request_id, status=status, code=code, message=message, data=None)

    def _serve_file(self, path: str) -> None:
        if not os.path.exists(path) or not os.path.isfile(path):
            self._json({"error": "not found"}, status=404)
            return
        ext = os.path.splitext(path)[1].lower()
        content_type = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".json": "application/json; charset=utf-8",
        }.get(ext, "application/octet-stream")
        with open(path, "rb") as fh:
            data = fh.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

        if getattr(self, "metrics", None) is not None:
            self.metrics.record(self.command, 200)
        self._log_response(200)

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def _is_authorized_v1(self, path: str) -> bool:
        if not path.startswith(API_PREFIX):
            return True
        if path in {f"{API_PREFIX}/healthz", f"{API_PREFIX}/readyz", f"{API_PREFIX}/metrics"}:
            return True
        if not self.api_token:
            return True
        auth = self.headers.get("Authorization", "")
        return auth == f"Bearer {self.api_token}"

    def _ready_status(self) -> Dict[str, Any]:
        checks = {
            "job_queue": self.queue is not None,
            "gateway_service": self.gateway_service is not None,
        }
        ready = all(checks.values())
        return {"status": "ready" if ready else "not_ready", "checks": checks}

    def _list_jobs(self) -> Any:
        return [asdict(job) for job in self.queue.store.list()]

    def _get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        record = self.queue.store.get(job_id)
        if not record:
            return None
        return asdict(record)

    def _handle_gateway_get_v1(self, path: str, request_id: str) -> bool:
        try:
            if path == f"{API_PREFIX}/gateway/status":
                self._json_v1(request_id=request_id, data={"gateway": self.gateway_service.status()})
                return True
            if path == f"{API_PREFIX}/gateway/account":
                self._json_v1(request_id=request_id, data={"account": self.gateway_service.account()})
                return True
            if path == f"{API_PREFIX}/gateway/positions":
                self._json_v1(request_id=request_id, data={"positions": self.gateway_service.positions()})
                return True
        except Exception as exc:
            self._error_v1(request_id=request_id, status=400, code=40001, message=str(exc))
            return True
        return False

    def _handle_gateway_post_v1(self, path: str, payload: Dict[str, Any], request_id: str) -> bool:
        try:
            if path == f"{API_PREFIX}/gateway/connect":
                status = self.gateway_service.connect(payload)
                self._json_v1(request_id=request_id, data={"gateway": status})
                self._audit(action="gateway.connect", resource="gateway", result="ok", request_id=request_id)
                return True
            if path == f"{API_PREFIX}/gateway/disconnect":
                status = self.gateway_service.disconnect()
                self._json_v1(request_id=request_id, data={"gateway": status})
                self._audit(action="gateway.disconnect", resource="gateway", result="ok", request_id=request_id)
                return True
            if path == f"{API_PREFIX}/gateway/order":
                result = self.gateway_service.submit_order(payload)
                self._json_v1(request_id=request_id, data=result, status=202)
                self._audit(
                    action="order.submit",
                    resource="gateway.order",
                    result="ok",
                    request_id=request_id,
                    details={"order_id": result.get("order_id"), "symbol": payload.get("symbol")},
                )
                return True
            if path == f"{API_PREFIX}/gateway/cancel":
                result = self.gateway_service.cancel_order(payload)
                self._json_v1(request_id=request_id, data=result)
                self._audit(
                    action="order.cancel",
                    resource="gateway.order",
                    result="ok" if result.get("cancelled") else "noop",
                    request_id=request_id,
                    details={"order_id": payload.get("order_id")},
                )
                return True
            if path == f"{API_PREFIX}/gateway/price":
                result = self.gateway_service.update_price(payload)
                self._json_v1(request_id=request_id, data=result)
                return True
        except Exception as exc:
            self._error_v1(request_id=request_id, status=400, code=40001, message=str(exc))
            return True
        return False

    def _handle_chart_data(self, request_id: str) -> None:
        """Serve OHLCV chart data for the frontend K-line chart."""
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        symbol = (qs.get("symbol") or [""])[0].strip()
        days = int((qs.get("days") or ["120"])[0])
        if not symbol:
            self._error_v1(request_id=request_id, status=400, code=40001, message="symbol is required")
            return
        days = max(10, min(days, 500))
        try:
            from datetime import datetime, timedelta
            end = datetime.now().strftime("%Y-%m-%d")
            start = (datetime.now() - timedelta(days=int(days * 1.5))).strftime("%Y-%m-%d")
            from src.data_sources.providers import AkshareProvider, DataProviderError
            provider = AkshareProvider()
            data_map = provider.load_stock_daily([symbol], start, end)
            if symbol not in data_map or data_map[symbol].empty:
                self._json_v1(request_id=request_id, data={"dates": [], "ohlc": [], "volumes": []})
                return
            df = data_map[symbol].tail(days)
            dates = [str(d.date()) if hasattr(d, "date") else str(d) for d in df.index]
            ohlc = []
            for _, row in df.iterrows():
                ohlc.append([float(row["open"]), float(row["close"]), float(row["low"]), float(row["high"])])
            volumes = [float(row.get("volume", 0)) for _, row in df.iterrows()]
            self._json_v1(request_id=request_id, data={"dates": dates, "ohlc": ohlc, "volumes": volumes})
        except Exception as exc:
            self._error_v1(request_id=request_id, status=500, code=50001, message=str(exc))

    def _handle_get_v1(self, path: str, request_id: str) -> None:
        if path == f"{API_PREFIX}/healthz":
            self._json_v1(request_id=request_id, data={"status": "ok"})
            return
        if path == f"{API_PREFIX}/readyz":
            self._json_v1(request_id=request_id, data=self._ready_status())
            return
        if path == f"{API_PREFIX}/metrics":
            self._json_v1(request_id=request_id, data=self.metrics.snapshot(self.queue))
            return

        if self._handle_gateway_get_v1(path, request_id):
            return

        if path == f"{API_PREFIX}/chart-data":
            self._handle_chart_data(request_id)
            return

        if path == f"{API_PREFIX}/jobs":
            self._json_v1(request_id=request_id, data={"jobs": self._list_jobs()})
            return

        if path.startswith(f"{API_PREFIX}/jobs/"):
            parts = [p for p in path.strip("/").split("/") if p]
            if len(parts) == 4:
                job_id = parts[3]
                record = self._get_job(job_id)
                if record is None:
                    self._error_v1(request_id=request_id, status=404, code=40401, message="job not found")
                    return
                self._json_v1(request_id=request_id, data={"job": record})
                return

        self._error_v1(request_id=request_id, status=404, code=40400, message="not found")

    def _handle_post_v1(self, path: str, payload: Dict[str, Any], request_id: str) -> None:
        if path == f"{API_PREFIX}/jobs/backtest":
            idem = self._idempotency_key(payload)
            job_id = self.queue.submit("backtest", run_backtest_job, payload, idempotency_key=idem)
            self._json_v1(request_id=request_id, data={"job_id": job_id}, status=202)
            self._audit(
                action="job.submit",
                resource="job.backtest",
                result="ok",
                request_id=request_id,
                details={"job_id": job_id, "idempotency_key": idem},
            )
            return

        if path == f"{API_PREFIX}/jobs/workflow":
            idem = self._idempotency_key(payload)
            job_id = self.queue.submit("workflow", run_workflow, payload, idempotency_key=idem)
            self._json_v1(request_id=request_id, data={"job_id": job_id}, status=202)
            self._audit(
                action="job.submit",
                resource="job.workflow",
                result="ok",
                request_id=request_id,
                details={"job_id": job_id, "idempotency_key": idem},
            )
            return

        if path.startswith(f"{API_PREFIX}/jobs/") and path.endswith("/cancel"):
            parts = [p for p in path.strip("/").split("/") if p]
            if len(parts) == 5 and parts[4] == "cancel":
                job_id = parts[3]
                try:
                    record = self.queue.cancel(job_id)
                    self._json_v1(request_id=request_id, data={"job": asdict(record)})
                    self._audit(
                        action="job.cancel",
                        resource="job",
                        result="ok",
                        request_id=request_id,
                        details={"job_id": job_id},
                    )
                except KeyError:
                    self._error_v1(request_id=request_id, status=404, code=40401, message="job not found")
                except RuntimeError as exc:
                    self._error_v1(request_id=request_id, status=409, code=40901, message=str(exc))
                return

        if self._handle_gateway_post_v1(path, payload, request_id):
            return

        self._error_v1(request_id=request_id, status=404, code=40400, message="not found")

    def do_GET(self) -> None:
        self._request_started_at = time.time()
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        request_id = self._request_id()
        self._current_request_id = request_id

        if path in ("/", "/index.html"):
            self._serve_file(os.path.join(WEB_ROOT, "index.html"))
            return
        if path.startswith("/assets/"):
            rel = path.replace("/assets/", "", 1).lstrip("/")
            safe_path = os.path.abspath(os.path.normpath(os.path.join(WEB_ROOT, rel)))
            if not safe_path.startswith(os.path.abspath(WEB_ROOT)):
                self._json({"error": "not found"}, status=404)
                return
            self._serve_file(safe_path)
            return

        if path == "/health":
            self._json({"status": "ok"})
            return
        if path == "/ready":
            self._json(self._ready_status())
            return
        if path == "/metrics":
            text = self.metrics.to_prometheus(self.queue)
            self._json(text, content_type="text/plain; version=0.0.4; charset=utf-8")
            return

        if path.startswith(API_PREFIX):
            if not self._is_authorized_v1(path):
                self._error_v1(request_id=request_id, status=401, code=40101, message="unauthorized")
                return
            self._handle_get_v1(path, request_id)
            return

        if path == "/gateway/status":
            self._json({"gateway": self.gateway_service.status()})
            return
        if path == "/gateway/account":
            try:
                self._json({"account": self.gateway_service.account()})
            except Exception as exc:
                self._json({"error": str(exc)}, status=400)
            return
        if path == "/gateway/positions":
            try:
                self._json({"positions": self.gateway_service.positions()})
            except Exception as exc:
                self._json({"error": str(exc)}, status=400)
            return
        if path == "/jobs":
            self._json({"jobs": self._list_jobs()})
            return
        if path.startswith("/jobs/"):
            job_id = path.split("/")[-1]
            record = self._get_job(job_id)
            if not record:
                self._json({"error": "job not found"}, status=404)
                return
            self._json({"job": record})
            return

        self._json({"error": "not found"}, status=404)

    def do_POST(self) -> None:
        self._request_started_at = time.time()
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        payload = self._read_json()
        request_id = self._request_id()
        self._current_request_id = request_id

        if path.startswith(API_PREFIX):
            if not self._is_authorized_v1(path):
                self._error_v1(request_id=request_id, status=401, code=40101, message="unauthorized")
                return
            self._handle_post_v1(path, payload, request_id)
            return

        if path == "/jobs/backtest":
            idem = self._idempotency_key(payload)
            job_id = self.queue.submit("backtest", run_backtest_job, payload, idempotency_key=idem)
            self._json({"job_id": job_id}, status=202)
            return
        if path == "/jobs/workflow":
            idem = self._idempotency_key(payload)
            job_id = self.queue.submit("workflow", run_workflow, payload, idempotency_key=idem)
            self._json({"job_id": job_id}, status=202)
            return
        if path == "/gateway/connect":
            try:
                status = self.gateway_service.connect(payload)
                self._json({"gateway": status})
            except Exception as exc:
                self._json({"error": str(exc)}, status=400)
            return
        if path == "/gateway/disconnect":
            status = self.gateway_service.disconnect()
            self._json({"gateway": status})
            return
        if path == "/gateway/order":
            try:
                result = self.gateway_service.submit_order(payload)
                self._json(result, status=202)
            except Exception as exc:
                self._json({"error": str(exc)}, status=400)
            return
        if path == "/gateway/cancel":
            try:
                result = self.gateway_service.cancel_order(payload)
                self._json(result)
            except Exception as exc:
                self._json({"error": str(exc)}, status=400)
            return
        if path == "/gateway/price":
            try:
                result = self.gateway_service.update_price(payload)
                self._json(result)
            except Exception as exc:
                self._json({"error": str(exc)}, status=400)
            return
        self._json({"error": "not found"}, status=404)


def create_api_server(
    *,
    host: str = "0.0.0.0",
    port: int = 8080,
    job_store_path: Optional[str] = "./cache/platform/jobs.json",
    max_workers: int = 4,
    api_token: Optional[str] = None,
    audit_log_path: Optional[str] = None,
) -> ThreadingHTTPServer:
    """Create the API server instance with configured dependencies."""
    store = JobStore(path=job_store_path)
    queue = JobQueue(store=store, max_workers=max_workers)
    gateway_service = GatewayService()
    metrics = APIMetrics()

    resolved_audit_path = audit_log_path
    if resolved_audit_path is None:
        resolved_audit_path = os.environ.get("PLATFORM_AUDIT_LOG")
    audit_logger = AuditLogger(path=resolved_audit_path) if resolved_audit_path else None

    class _Handler(PlatformAPIHandler):
        pass

    _Handler.queue = queue
    _Handler.gateway_service = gateway_service
    _Handler.metrics = metrics
    _Handler.api_token = api_token if api_token is not None else os.environ.get("PLATFORM_API_TOKEN")
    _Handler.audit_logger = audit_logger

    server = ThreadingHTTPServer((host, port), _Handler)
    # Attach runtime components for controlled shutdown/testing.
    server.job_queue = queue  # type: ignore[attr-defined]
    server.gateway_service = gateway_service  # type: ignore[attr-defined]
    server.api_metrics = metrics  # type: ignore[attr-defined]
    server.audit_logger = audit_logger  # type: ignore[attr-defined]
    return server


def run_api_server(
    *,
    host: str = "0.0.0.0",
    port: int = 8080,
    job_store_path: Optional[str] = "./cache/platform/jobs.json",
    max_workers: int = 4,
    api_token: Optional[str] = None,
    audit_log_path: Optional[str] = None,
) -> None:
    server = create_api_server(
        host=host,
        port=port,
        job_store_path=job_store_path,
        max_workers=max_workers,
        api_token=api_token,
        audit_log_path=audit_log_path,
    )
    listen_host, listen_port = server.server_address
    print(f"[platform] API server listening on http://{listen_host}:{listen_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        server.job_queue.shutdown()  # type: ignore[attr-defined]

