"""
Run the platform console paper-trading feature demo.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.platform.api_server import APIMetrics, GatewayService, MonitorService
from src.platform.demo import run_paper_trading_demo, write_demo_report
from src.platform.job_queue import JobQueue, JobStore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a deterministic paper-trading console demo"
    )
    parser.add_argument("--symbol", default="600519.SH")
    parser.add_argument("--quantity", type=float, default=100.0)
    parser.add_argument("--entry-price", type=float, default=100.0)
    parser.add_argument("--entry-fill-price", type=float, default=99.5)
    parser.add_argument("--mark-price", type=float, default=101.2)
    parser.add_argument("--exit-limit-price", type=float, default=120.0)
    parser.add_argument("--out", default="report/platform_console_demo.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    queue = JobQueue(store=JobStore(), max_workers=1)
    try:
        report = run_paper_trading_demo(
            GatewayService(),
            queue=queue,
            monitor_service=MonitorService(),
            metrics=APIMetrics(),
            symbol=args.symbol,
            quantity=args.quantity,
            entry_price=args.entry_price,
            entry_fill_price=args.entry_fill_price,
            mark_price=args.mark_price,
            exit_limit_price=args.exit_limit_price,
        )
        out_path = write_demo_report(report, Path(args.out))
        print(
            json.dumps(
                {
                    "ok": report["ok"],
                    "summary": report["summary"],
                    "steps": len(report["steps"]),
                    "output": str(out_path),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        queue.shutdown()


if __name__ == "__main__":
    main()
