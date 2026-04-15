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
from datetime import date, datetime
from enum import Enum
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from src.core.audit import AuditLogger, audit_event
from src.core.logger import get_logger
from src.core.monitoring import SystemMonitor
from src.core.trading_gateway import BrokerType, GatewayConfig, TradingGateway, TradingMode
from src.core.interfaces import OrderTypeEnum
from src.platform.backtest_task import run_backtest_job
from src.platform.job_queue import JobQueue, JobStore
from src.platform.orchestrator import run_workflow

WEB_ROOT = os.path.join(os.path.dirname(__file__), "web")
API_PREFIX = "/api/v1"

logger = get_logger("platform.api")


def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {k: _to_jsonable(v) for k, v in asdict(value).items()}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
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


class MonitorService:
    """On-demand monitor snapshots for the web console and API consumers."""

    def __init__(self, *, refresh_interval: float = 5.0, history_limit: int = 120) -> None:
        self._lock = threading.Lock()
        self._refresh_interval = refresh_interval
        self._history_limit = history_limit
        self._monitor = SystemMonitor(check_interval=refresh_interval)
        self._last_refresh_at = 0.0

    def summary(
        self,
        *,
        queue: JobQueue,
        gateway_service: "GatewayService",
        metrics: APIMetrics,
        jobs_limit: int = 10,
        orders_limit: int = 20,
        trades_limit: int = 20,
    ) -> Dict[str, Any]:
        with self._lock:
            self._refresh_locked()
            system = _to_jsonable(self._monitor.get_current_metrics())
            alerts = _to_jsonable(self._monitor.get_recent_alerts(10))

        gateway = gateway_service.snapshot(orders_limit=orders_limit, trades_limit=trades_limit)
        jobs = self._recent_jobs(queue, jobs_limit)
        queue_metrics = queue.metrics()
        api_metrics = metrics.snapshot(queue)

        return {
            "status": self._overall_status(gateway=gateway, alerts=alerts),
            "timestamp": datetime.now().isoformat(),
            "system": system,
            "alerts": alerts,
            "gateway": gateway,
            "job_queue": queue_metrics,
            "api": api_metrics,
            "jobs": jobs,
        }

    def history(self, *, limit: int = 30) -> List[Dict[str, Any]]:
        with self._lock:
            self._refresh_locked()
            entries = list(self._monitor.metrics_history)
        return _to_jsonable(entries[-limit:][::-1])

    def alerts(self, *, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            self._refresh_locked()
            alerts = self._monitor.get_recent_alerts(limit)
        return _to_jsonable(list(reversed(alerts)))

    def _refresh_locked(self) -> None:
        now = time.monotonic()
        if self._monitor.metrics_history and (now - self._last_refresh_at) < self._refresh_interval:
            return

        metrics = self._monitor.collect_metrics()
        self._monitor.metrics_history.append(metrics)
        if len(self._monitor.metrics_history) > self._history_limit:
            self._monitor.metrics_history = self._monitor.metrics_history[-self._history_limit :]

        alerts = self._monitor.check_thresholds(metrics)
        for alert in alerts:
            self._monitor.alerts.append(alert)
            self._monitor._handle_alert(alert)
        if len(self._monitor.alerts) > self._history_limit:
            self._monitor.alerts = self._monitor.alerts[-self._history_limit :]

        self._last_refresh_at = now

    @staticmethod
    def _recent_jobs(queue: JobQueue, limit: int) -> List[Dict[str, Any]]:
        jobs = sorted(queue.store.list(), key=lambda job: job.created_at, reverse=True)
        return [_to_jsonable(asdict(job)) for job in jobs[:limit]]

    @staticmethod
    def _overall_status(gateway: Dict[str, Any], alerts: List[Dict[str, Any]]) -> str:
        if any(alert.get("level") in {"ERROR", "CRITICAL"} for alert in alerts):
            return "critical"
        if alerts:
            return "warning"
        gateway_status = gateway.get("status", {})
        if gateway_status.get("connected"):
            return "healthy"
        return "degraded"


class GatewayService:
    """Thread-safe wrapper for a singleton trading gateway instance."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._gateway: Optional[TradingGateway] = None
        self._last_error: Optional[str] = None
        self._connected_at: Optional[str] = None

    def connect(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        config = self._build_config(payload)
        gateway = TradingGateway(config)
        ok = gateway.connect()
        previous_gateway: Optional[TradingGateway] = None
        with self._lock:
            previous_gateway = self._gateway
            if ok or previous_gateway is None:
                self._gateway = gateway
            self._last_error = None if ok else "connect_failed"
            if ok:
                self._connected_at = datetime.now().isoformat()
        if ok and previous_gateway and previous_gateway is not gateway:
            try:
                previous_gateway.disconnect()
            except Exception:
                logger.warning("gateway.previous_disconnect_failed")
        return self.status()

    def disconnect(self) -> Dict[str, Any]:
        gateway: Optional[TradingGateway] = None
        with self._lock:
            if not self._gateway:
                return {"status": "disconnected"}
            gateway = self._gateway
        if gateway is not None:
            gateway.disconnect()
        with self._lock:
            self._connected_at = None
            return self.status()

    def status(self) -> Dict[str, Any]:
        with self._lock:
            if not self._gateway:
                return {"status": "disconnected", "connected": False, "mode": "-", "broker": "-", "last_error": self._last_error}
            return {
                "status": self._gateway.status.value,
                "connected": self._gateway.is_connected(),
                "mode": self._gateway.config.mode.value,
                "broker": self._gateway.config.broker.value,
                "account": self._gateway.config.account,
                "connected_at": self._connected_at,
                "last_error": self._last_error,
            }

    def account(self) -> Dict[str, Any]:
        gateway = self._require_gateway()
        return _to_jsonable(gateway.get_account())

    def positions(self) -> Dict[str, Any]:
        gateway = self._require_gateway()
        return _to_jsonable(gateway.get_positions())

    def positions_list(self) -> List[Dict[str, Any]]:
        gateway = self._require_gateway()
        return self._positions_list(gateway)

    def orders(self, *, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        gateway = self._require_gateway()
        return _to_jsonable(gateway.get_orders(symbol=symbol))

    def trades(self, *, symbol: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        gateway = self._require_gateway()
        return _to_jsonable(gateway.get_trades(symbol=symbol, limit=limit))

    def safe_account(self) -> Optional[Dict[str, Any]]:
        gateway = self._optional_gateway()
        if gateway is None:
            return None
        try:
            return _to_jsonable(gateway.get_account())
        except Exception as exc:
            return {"error": str(exc)}

    def safe_positions(self) -> List[Dict[str, Any]]:
        gateway = self._optional_gateway()
        if gateway is None:
            return []
        try:
            return self._positions_list(gateway)
        except Exception as exc:
            return [{"error": str(exc)}]

    def safe_orders(self, *, symbol: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        gateway = self._optional_gateway()
        if gateway is None:
            return []
        try:
            orders = gateway.get_orders(symbol=symbol)
            if limit is not None and limit >= 0:
                orders = orders[:limit]
            return _to_jsonable(orders)
        except Exception as exc:
            return [{"error": str(exc)}]

    def safe_trades(self, *, symbol: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        gateway = self._optional_gateway()
        if gateway is None:
            return []
        try:
            return _to_jsonable(gateway.get_trades(symbol=symbol, limit=limit))
        except Exception as exc:
            return [{"error": str(exc)}]

    def snapshot(self, *, orders_limit: int = 20, trades_limit: int = 20) -> Dict[str, Any]:
        return {
            "status": self.status(),
            "account": self.safe_account(),
            "positions": self.safe_positions(),
            "orders": self.safe_orders(limit=orders_limit),
            "trades": self.safe_trades(limit=trades_limit),
        }

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

    def _optional_gateway(self) -> Optional[TradingGateway]:
        with self._lock:
            return self._gateway

    @staticmethod
    def _positions_list(gateway: TradingGateway) -> List[Dict[str, Any]]:
        positions = gateway.get_positions()
        return _to_jsonable(list(positions.values()))

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
    monitor_service: MonitorService
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
            body = json.dumps(_to_jsonable(payload), ensure_ascii=False).encode("utf-8")
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

    def _query_params(self) -> Dict[str, List[str]]:
        return parse_qs(urlparse(self.path).query)

    def _query_int(self, name: str, default: int, *, minimum: int = 0, maximum: int = 1000) -> int:
        raw = (self._query_params().get(name) or [str(default)])[0]
        try:
            value = int(raw)
        except (TypeError, ValueError):
            value = default
        return max(minimum, min(maximum, value))

    def _handle_gateway_get_v1(self, path: str, request_id: str) -> bool:
        query = self._query_params()
        symbol = ((query.get("symbol") or [""])[0] or "").strip() or None
        limit = self._query_int("limit", 20, minimum=1, maximum=500)
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
            if path == f"{API_PREFIX}/gateway/orders":
                self._json_v1(request_id=request_id, data={"orders": self.gateway_service.orders(symbol=symbol)})
                return True
            if path == f"{API_PREFIX}/gateway/trades":
                self._json_v1(
                    request_id=request_id,
                    data={"trades": self.gateway_service.trades(symbol=symbol, limit=limit)},
                )
                return True
            if path == f"{API_PREFIX}/gateway/snapshot":
                self._json_v1(
                    request_id=request_id,
                    data={"gateway": self.gateway_service.snapshot(orders_limit=limit, trades_limit=limit)},
                )
                return True
        except Exception as exc:
            self._error_v1(request_id=request_id, status=400, code=40001, message=str(exc))
            return True
        return False

    def _handle_monitor_get_v1(self, path: str, request_id: str) -> bool:
        limit = self._query_int("limit", 20, minimum=1, maximum=500)
        try:
            if path == f"{API_PREFIX}/monitor/summary":
                self._json_v1(
                    request_id=request_id,
                    data={
                        "monitor": self.monitor_service.summary(
                            queue=self.queue,
                            gateway_service=self.gateway_service,
                            metrics=self.metrics,
                            jobs_limit=min(limit, 50),
                            orders_limit=limit,
                            trades_limit=limit,
                        )
                    },
                )
                return True
            if path == f"{API_PREFIX}/monitor/history":
                self._json_v1(request_id=request_id, data={"history": self.monitor_service.history(limit=limit)})
                return True
            if path == f"{API_PREFIX}/monitor/alerts":
                self._json_v1(request_id=request_id, data={"alerts": self.monitor_service.alerts(limit=limit)})
                return True
        except Exception as exc:
            self._error_v1(request_id=request_id, status=500, code=50001, message=str(exc))
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

        if self._handle_monitor_get_v1(path, request_id):
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
        if path == "/gateway/orders":
            symbol = ((self._query_params().get("symbol") or [""])[0] or "").strip() or None
            try:
                self._json({"orders": self.gateway_service.orders(symbol=symbol)})
            except Exception as exc:
                self._json({"error": str(exc)}, status=400)
            return
        if path == "/gateway/trades":
            symbol = ((self._query_params().get("symbol") or [""])[0] or "").strip() or None
            limit = self._query_int("limit", 20, minimum=1, maximum=500)
            try:
                self._json({"trades": self.gateway_service.trades(symbol=symbol, limit=limit)})
            except Exception as exc:
                self._json({"error": str(exc)}, status=400)
            return
        if path == "/gateway/snapshot":
            limit = self._query_int("limit", 20, minimum=1, maximum=500)
            self._json({"gateway": self.gateway_service.snapshot(orders_limit=limit, trades_limit=limit)})
            return
        if path == "/monitor/summary":
            limit = self._query_int("limit", 20, minimum=1, maximum=500)
            self._json(
                {
                    "monitor": self.monitor_service.summary(
                        queue=self.queue,
                        gateway_service=self.gateway_service,
                        metrics=self.metrics,
                        jobs_limit=min(limit, 50),
                        orders_limit=limit,
                        trades_limit=limit,
                    )
                }
            )
            return
        if path == "/monitor/history":
            limit = self._query_int("limit", 20, minimum=1, maximum=500)
            self._json({"history": self.monitor_service.history(limit=limit)})
            return
        if path == "/monitor/alerts":
            limit = self._query_int("limit", 20, minimum=1, maximum=500)
            self._json({"alerts": self.monitor_service.alerts(limit=limit)})
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
    monitor_service = MonitorService()
    metrics = APIMetrics()

    resolved_audit_path = audit_log_path
    if resolved_audit_path is None:
        resolved_audit_path = os.environ.get("PLATFORM_AUDIT_LOG")
    audit_logger = AuditLogger(path=resolved_audit_path) if resolved_audit_path else None

    class _Handler(PlatformAPIHandler):
        pass

    _Handler.queue = queue
    _Handler.gateway_service = gateway_service
    _Handler.monitor_service = monitor_service
    _Handler.metrics = metrics
    _Handler.api_token = api_token if api_token is not None else os.environ.get("PLATFORM_API_TOKEN")
    _Handler.audit_logger = audit_logger

    server = ThreadingHTTPServer((host, port), _Handler)
    # Attach runtime components for controlled shutdown/testing.
    server.job_queue = queue  # type: ignore[attr-defined]
    server.gateway_service = gateway_service  # type: ignore[attr-defined]
    server.monitor_service = monitor_service  # type: ignore[attr-defined]
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
