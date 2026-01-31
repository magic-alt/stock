"""
Minimal HTTP API server for platform job orchestration.
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from src.platform.backtest_task import run_backtest_job
from src.platform.job_queue import JobQueue, JobStore
from src.platform.orchestrator import run_workflow


class PlatformAPIHandler(BaseHTTPRequestHandler):
    queue: JobQueue

    def _json(self, payload: Dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._json({"status": "ok"})
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

    class _Handler(PlatformAPIHandler):
        queue = queue

    server = ThreadingHTTPServer((host, port), _Handler)
    print(f"[platform] API server listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        queue.shutdown()
