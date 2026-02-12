"""
Run the lightweight platform API server.
"""
from __future__ import annotations

import argparse
import os
import sys

# Ensure repo root is on sys.path when running as a script.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

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
        default=None,
        help="Optional Bearer token for /api/v1 endpoints (fallback: PLATFORM_API_TOKEN env)",
    )
    parser.add_argument(
        "--audit-log",
        default=None,
        help="Optional audit log path (fallback: PLATFORM_AUDIT_LOG env)",
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


if __name__ == "__main__":
    main()
