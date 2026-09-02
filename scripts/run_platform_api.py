"""Run the platform API server through the typed settings SSOT.

Runtime precedence is ``CLI > environment > config.yaml > safe defaults``.
Use ``--legacy-v1`` only when the older ThreadingHTTPServer compatibility
surface is needed.
"""
from __future__ import annotations

import argparse
import os
import sys

# Ensure repo root is on sys.path when running as a script.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.core.settings import load_platform_settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Platform API server")
    parser.add_argument("--config", default=None, help="Optional config.yaml path (fallback: PLATFORM_CONFIG)")
    parser.add_argument("--host", default=None, help="API bind host")
    parser.add_argument("--port", type=int, default=None, help="API bind port")
    parser.add_argument(
        "--jobs",
        default=None,
        help="Job store path/DSN (.json, SQLite, redis:// or postgresql://)",
    )
    parser.add_argument("--workers", type=int, default=None, help="Job queue worker count")
    parser.add_argument("--api-token", default=None, help="Bootstrap Bearer token")
    parser.add_argument("--audit-log", default=None, help="Audit log path")
    parser.add_argument(
        "--auth-disabled",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Explicitly enable/disable API authentication (local development only when disabled)",
    )
    parser.add_argument(
        "--legacy-v1",
        action="store_true",
        help="Run the legacy /api/v1 ThreadingHTTPServer instead of FastAPI v2",
    )
    return parser.parse_args()


def _cli_overrides(args: argparse.Namespace) -> dict:
    api = {}
    platform = {}
    if args.host is not None:
        api["host"] = args.host
    if args.port is not None:
        api["port"] = args.port
    if args.api_token is not None:
        api["token"] = args.api_token
    if args.audit_log is not None:
        api["audit_log"] = args.audit_log
    if args.auth_disabled is not None:
        api["auth_disabled"] = args.auth_disabled
    if args.jobs is not None:
        platform["job_store"] = args.jobs
    if args.workers is not None:
        platform["job_max_workers"] = args.workers

    overrides = {}
    if api:
        overrides["api"] = api
    if platform:
        overrides["platform"] = platform
    return overrides


def main() -> None:
    args = parse_args()
    settings = load_platform_settings(
        config_path=args.config,
        cli_overrides=_cli_overrides(args),
    )

    if args.legacy_v1:
        from src.platform.api_server import run_api_server

        run_api_server(
            host=settings.api.host,
            port=settings.api.port,
            job_store_path=settings.platform.job_store,
            max_workers=settings.platform.job_max_workers,
            api_token=settings.api.token.get_secret_value() or None,
            audit_log_path=settings.api.audit_log,
        )
        return

    try:
        import uvicorn
    except ImportError as exc:
        raise SystemExit("FastAPI v2 server requires uvicorn: pip install 'uvicorn[standard]'") from exc

    from src.platform.api_v2 import create_app

    app = create_app(settings=settings)
    uvicorn.run(app, host=settings.api.host, port=settings.api.port)


if __name__ == "__main__":
    main()
