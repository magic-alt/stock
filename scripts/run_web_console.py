"""Run the local WebUI.

Default mode follows the daily_stock_analysis style: build or reuse the Vite
bundle, serve it from the FastAPI backend, and open one local URL. Use --dev
when you need the Vite development server with hot reload.
"""
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
FRONTEND_DIST = FRONTEND / "dist"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the stock WebUI")
    parser.add_argument("--host", default=os.getenv("WEBUI_HOST", os.getenv("API_HOST", "127.0.0.1")))
    parser.add_argument("--port", type=int, default=int(os.getenv("WEBUI_PORT", os.getenv("API_PORT", "8001"))))
    parser.add_argument("--jobs", default=os.getenv("PLATFORM_JOB_STORE", "./cache/platform/jobs.json"))
    parser.add_argument("--no-open", action="store_true", help="Do not open the browser automatically")
    parser.add_argument("--no-build", action="store_true", help="Do not build frontend/dist if it is missing")
    parser.add_argument("--rebuild", action="store_true", help="Always run npm run build before starting")
    parser.add_argument("--npm-install", action="store_true", help="Run npm install in frontend/ before building")
    parser.add_argument("--dev", action="store_true", help="Run Vite dev server instead of serving frontend/dist")
    parser.add_argument("--frontend-host", default=os.getenv("FRONTEND_HOST", "127.0.0.1"))
    parser.add_argument("--frontend-port", type=int, default=int(os.getenv("FRONTEND_PORT", "3000")))
    return parser.parse_args()


def wait_for_url(url: str, *, timeout: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status < 500:
                    return True
        except (OSError, urllib.error.URLError):
            time.sleep(0.5)
    return False


def run_checked(command: Sequence[str], *, cwd: Path, env: dict[str, str]) -> None:
    print("+ " + " ".join(command))
    subprocess.run(list(command), cwd=str(cwd), env=env, check=True)


def ensure_frontend_dist(args: argparse.Namespace, env: dict[str, str]) -> None:
    index_file = FRONTEND_DIST / "index.html"
    if args.rebuild or not index_file.is_file():
        if args.no_build:
            raise SystemExit(
                f"frontend bundle not found: {index_file}. "
                "Run npm run build in frontend/ or omit --no-build."
            )
        if args.npm_install or not (FRONTEND / "node_modules").is_dir():
            run_checked(["npm", "install"], cwd=FRONTEND, env=env)
        run_checked(["npm", "run", "build"], cwd=FRONTEND, env=env)


def open_when_ready(url: str) -> None:
    if wait_for_url(url, timeout=30):
        webbrowser.open(url)


def start_process(command: Sequence[str], *, cwd: Path, env: dict[str, str]) -> subprocess.Popen:
    return subprocess.Popen(list(command), cwd=str(cwd), env=env, text=True)


def terminate(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def run_dev_mode(args: argparse.Namespace, env: dict[str, str]) -> int:
    api_url = f"http://{args.host}:{args.port}"
    frontend_url = f"http://{args.frontend_host}:{args.frontend_port}/"
    env.setdefault("VITE_API_BASE_URL", api_url)

    api_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "src.platform.api_v2:app",
        "--host",
        args.host,
        "--port",
        str(args.port),
    ]
    frontend_cmd = [
        "npm",
        "run",
        "dev",
        "--",
        "--host",
        args.frontend_host,
        "--port",
        str(args.frontend_port),
    ]
    processes: list[subprocess.Popen] = []

    def stop_all(signum: int | None = None, frame: object | None = None) -> None:
        for process in reversed(processes):
            terminate(process)

    signal.signal(signal.SIGINT, stop_all)
    signal.signal(signal.SIGTERM, stop_all)

    try:
        health_url = f"{api_url}/api/v2/health"
        if wait_for_url(health_url, timeout=1):
            print(f"Using existing API: {api_url}")
        else:
            print(f"Starting API: {api_url}")
            processes.append(start_process(api_cmd, cwd=ROOT, env=env))
            if not wait_for_url(health_url, timeout=30):
                raise SystemExit(f"API did not become ready: {health_url}")

        if wait_for_url(frontend_url, timeout=1):
            print(f"Using existing frontend: {frontend_url}")
        else:
            print(f"Starting frontend: {frontend_url}")
            processes.append(start_process(frontend_cmd, cwd=FRONTEND, env=env))
            if not wait_for_url(frontend_url, timeout=30):
                raise SystemExit(f"Frontend did not become ready: {frontend_url}")

        print(f"Web console is ready: {frontend_url}")
        if not args.no_open:
            webbrowser.open(frontend_url)
        if not processes:
            return 0
        while all(process.poll() is None for process in processes):
            time.sleep(1)
        return next((process.returncode or 0 for process in processes if process.poll() is not None), 0)
    finally:
        stop_all()


def run_static_mode(args: argparse.Namespace, env: dict[str, str]) -> int:
    ensure_frontend_dist(args, env)
    env["PLATFORM_FRONTEND_DIST"] = str(FRONTEND_DIST)
    url = f"http://{args.host}:{args.port}/"
    health_url = f"http://{args.host}:{args.port}/api/v2/health"

    if wait_for_url(health_url, timeout=1):
        print(f"Using existing WebUI: {url}")
        if not args.no_open:
            webbrowser.open(url)
        return 0

    print(f"Starting WebUI: {url}")
    print(f"API docs: http://{args.host}:{args.port}/api/v2/docs")
    if not args.no_open:
        threading.Thread(target=open_when_ready, args=(url,), daemon=True).start()

    try:
        import uvicorn
    except ImportError as exc:
        raise SystemExit("FastAPI WebUI requires uvicorn: pip install 'uvicorn[standard]'") from exc

    uvicorn.run("src.platform.api_v2:app", host=args.host, port=args.port)
    return 0


def main() -> int:
    args = parse_args()
    if not FRONTEND.exists():
        raise SystemExit(f"frontend directory not found: {FRONTEND}")

    env = os.environ.copy()
    env["PLATFORM_JOB_STORE"] = args.jobs
    if args.dev:
        return run_dev_mode(args, env)
    return run_static_mode(args, env)


if __name__ == "__main__":
    raise SystemExit(main())
