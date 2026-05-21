"""Console entry points for the web distribution."""
from __future__ import annotations

import argparse
import os

from src.platform.api_server import run_api_server


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Platform API server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument(
        "--jobs",
        default="./cache/platform/jobs.json",
        help="Job store path (.json for JSON store, .db/sqlite:///path for SQLite store)",
    )
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--api-token",
        default=os.getenv("PLATFORM_API_TOKEN"),
        help="Optional Bearer token for /api/v1 endpoints.",
    )
    parser.add_argument(
        "--audit-log",
        default=os.getenv("PLATFORM_AUDIT_LOG"),
        help="Optional audit log path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_api_server(
        host=args.host,
        port=args.port,
        job_store_path=args.jobs,
        max_workers=args.workers,
        api_token=args.api_token,
        audit_log_path=args.audit_log,
    )


__all__ = ["main", "parse_args"]
