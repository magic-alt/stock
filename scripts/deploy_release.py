#!/usr/bin/env python3
"""
Build and deploy the production stack with Docker Compose.

Usage:
    python scripts/deploy_release.py
    python scripts/deploy_release.py --skip-build
    python scripts/deploy_release.py --down
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deploy the production stack with Docker Compose")
    parser.add_argument("--compose-file", default="docker-compose.yml", help="Compose file path")
    parser.add_argument("--skip-build", action="store_true", help="Skip image rebuild")
    parser.add_argument("--timeout", type=int, default=300, help="Health-check timeout in seconds")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000/api/v2/health")
    parser.add_argument("--frontend-url", default="http://127.0.0.1:3000")
    parser.add_argument("--down", action="store_true", help="Stop the deployed stack")
    return parser.parse_args()


def run(cmd: list[str]) -> None:
    print(f"[deploy] {' '.join(cmd)}")
    subprocess.run(cmd, cwd=PROJECT_ROOT, check=True)


def wait_http(url: str, timeout: int) -> None:
    deadline = time.time() + timeout
    last_error = "timeout"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                if 200 <= resp.status < 500:
                    print(f"[deploy] healthy: {url} ({resp.status})")
                    return
        except urllib.error.URLError as exc:
            last_error = str(exc)
        except Exception as exc:  # pragma: no cover - defensive
            last_error = str(exc)
        time.sleep(2)
    raise RuntimeError(f"Health check failed for {url}: {last_error}")


def main() -> int:
    args = parse_args()
    compose_file = str((PROJECT_ROOT / args.compose_file).resolve())

    if shutil.which("docker") is None:
        raise RuntimeError("docker is not installed or not on PATH")

    if args.down:
        run(["docker", "compose", "-f", compose_file, "down"])
        return 0

    compose_cmd = ["docker", "compose", "-f", compose_file, "up", "-d"]
    if not args.skip_build:
        compose_cmd.append("--build")

    run(compose_cmd)
    wait_http(args.api_url, args.timeout)
    wait_http(args.frontend_url, args.timeout)
    print("[deploy] stack is up")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[deploy] failed: {exc}", file=sys.stderr)
        raise
