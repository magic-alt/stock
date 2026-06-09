"""Run the platform API server.

By default this starts the FastAPI v2 application documented in README and
served by Docker. Use ``--legacy-v1`` only when the older ThreadingHTTPServer
compatibility surface is needed.
"""
from __future__ import annotations

import argparse
import os
import sys

# Ensure repo root is on sys.path when running as a script.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Platform API server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
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
    parser.add_argument(
        "--legacy-v1",
        action="store_true",
        help="Run the legacy /api/v1 ThreadingHTTPServer instead of FastAPI v2",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.legacy_v1:
        from src.platform.api_server import run_api_server

        run_api_server(
            host=args.host,
            port=args.port,
            job_store_path=args.jobs,
            max_workers=args.workers,
            api_token=args.api_token,
            audit_log_path=args.audit_log,
        )
        return

    os.environ["PLATFORM_JOB_STORE"] = args.jobs
    os.environ["PLATFORM_JOB_MAX_WORKERS"] = str(args.workers)
    if args.api_token:
        os.environ["PLATFORM_API_TOKEN"] = args.api_token
    if args.audit_log:
        os.environ["PLATFORM_AUDIT_LOG"] = args.audit_log

    try:
        import uvicorn
    except ImportError as exc:
        raise SystemExit("FastAPI v2 server requires uvicorn: pip install 'uvicorn[standard]'") from exc

    uvicorn.run("src.platform.api_v2:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
