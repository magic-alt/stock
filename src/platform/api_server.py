"""
Minimal HTTP API server for platform job orchestration.
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, is_dataclass
from enum import Enum
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from src.core.trading_gateway import TradingGateway, GatewayConfig, TradingMode, BrokerType
from src.core.interfaces import OrderTypeEnum
from src.platform.backtest_task import run_backtest_job
from src.platform.job_queue import JobQueue, JobStore
from src.platform.orchestrator import run_workflow

WEB_ROOT = os.path.join(os.path.dirname(__file__), "web")


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

    def _json(self, payload: Dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            self._serve_file(os.path.join(WEB_ROOT, "index.html"))
            return
        if parsed.path.startswith("/assets/"):
            rel = parsed.path.replace("/assets/", "", 1).lstrip("/")
            safe_path = os.path.abspath(os.path.normpath(os.path.join(WEB_ROOT, rel)))
            if not safe_path.startswith(os.path.abspath(WEB_ROOT)):
                self._json({"error": "not found"}, status=404)
                return
            self._serve_file(safe_path)
            return
        if parsed.path == "/health":
            self._json({"status": "ok"})
            return
        if parsed.path == "/gateway/status":
            self._json({"gateway": self.gateway_service.status()})
            return
        if parsed.path == "/gateway/account":
            try:
                self._json({"account": self.gateway_service.account()})
            except Exception as exc:
                self._json({"error": str(exc)}, status=400)
            return
        if parsed.path == "/gateway/positions":
            try:
                self._json({"positions": self.gateway_service.positions()})
            except Exception as exc:
                self._json({"error": str(exc)}, status=400)
            return
        if parsed.path == "/jobs":
            jobs = [job.__dict__ for job in self.queue.store.list()]
            self._json({"jobs": jobs})
            return
        if parsed.path.startswith("/jobs/"):
            job_id = parsed.path.split("/")[-1]
            record = self.queue.store.get(job_id)
            if not record:
                self._json({"error": "job not found"}, status=404)
                return
            self._json({"job": record.__dict__})
            return
        self._json({"error": "not found"}, status=404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        payload = self._read_json()
        if parsed.path == "/jobs/backtest":
            job_id = self.queue.submit("backtest", run_backtest_job, payload)
            self._json({"job_id": job_id}, status=202)
            return
        if parsed.path == "/jobs/workflow":
            job_id = self.queue.submit("workflow", run_workflow, payload)
            self._json({"job_id": job_id}, status=202)
            return
        if parsed.path == "/gateway/connect":
            try:
                status = self.gateway_service.connect(payload)
                self._json({"gateway": status})
            except Exception as exc:
                self._json({"error": str(exc)}, status=400)
            return
        if parsed.path == "/gateway/disconnect":
            status = self.gateway_service.disconnect()
            self._json({"gateway": status})
            return
        if parsed.path == "/gateway/order":
            try:
                result = self.gateway_service.submit_order(payload)
                self._json(result, status=202)
            except Exception as exc:
                self._json({"error": str(exc)}, status=400)
            return
        if parsed.path == "/gateway/cancel":
            try:
                result = self.gateway_service.cancel_order(payload)
                self._json(result)
            except Exception as exc:
                self._json({"error": str(exc)}, status=400)
            return
        if parsed.path == "/gateway/price":
            try:
                result = self.gateway_service.update_price(payload)
                self._json(result)
            except Exception as exc:
                self._json({"error": str(exc)}, status=400)
            return
        self._json({"error": "not found"}, status=404)


def run_api_server(
    *,
    host: str = "0.0.0.0",
    port: int = 8080,
    job_store_path: Optional[str] = "./cache/platform/jobs.json",
    max_workers: int = 4,
) -> None:
    store = JobStore(path=job_store_path)
    queue = JobQueue(store=store, max_workers=max_workers)
    gateway_service = GatewayService()

    class _Handler(PlatformAPIHandler):
        pass

    _Handler.queue = queue
    _Handler.gateway_service = gateway_service
    server = ThreadingHTTPServer((host, port), _Handler)
    print(f"[platform] API server listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        queue.shutdown()
