"""
Run the lightweight platform API server.
"""
from __future__ import annotations

import argparse

from src.platform.api_server import run_api_server


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Platform API server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--jobs", default="./cache/platform/jobs.json")
    parser.add_argument("--workers", type=int, default=4)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_api_server(host=args.host, port=args.port, job_store_path=args.jobs, max_workers=args.workers)


if __name__ == "__main__":
    main()
