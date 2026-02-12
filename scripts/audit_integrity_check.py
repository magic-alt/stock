"""
Audit integrity checker.

Validates hash-chain integrity for append-only audit logs and optionally
checks freshness constraints for the latest record.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _parse_iso_z(value: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _load_last_timestamp(path: str) -> Optional[datetime]:
    if not os.path.exists(path):
        return None
    last: Optional[datetime] = None
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts_raw = str(record.get("timestamp", "")).strip()
            ts = _parse_iso_z(ts_raw)
            if ts is not None:
                last = ts
    return last


def run_check(path: str, max_age_minutes: Optional[float] = None) -> Dict[str, Any]:
    from src.core.audit import AuditLogger

    logger = AuditLogger(path=path, chain_hash=True)
    chain_ok = logger.verify()
    last_ts = _load_last_timestamp(path)

    stale = False
    age_seconds = None
    if max_age_minutes is not None and last_ts is not None:
        now = datetime.now(timezone.utc)
        age_seconds = max(0.0, (now - last_ts).total_seconds())
        stale = age_seconds > (max_age_minutes * 60.0)

    status = "ok"
    if not chain_ok:
        status = "failed"
    elif stale:
        status = "stale"

    return {
        "status": status,
        "path": path,
        "chain_ok": chain_ok,
        "last_timestamp": last_ts.isoformat() if last_ts else None,
        "max_age_minutes": max_age_minutes,
        "age_seconds": age_seconds,
        "stale": stale,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit log integrity checker")
    parser.add_argument("--path", default="./logs/audit.log", help="Audit log path")
    parser.add_argument(
        "--max-age-minutes",
        type=float,
        default=None,
        help="Mark stale when latest record is older than threshold",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero exit code on stale status in addition to failed",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_check(args.path, max_age_minutes=args.max_age_minutes)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"status={result['status']} path={result['path']}")
        print(f"chain_ok={result['chain_ok']} last_timestamp={result['last_timestamp']}")
        if result["age_seconds"] is not None:
            print(f"age_seconds={result['age_seconds']:.1f} stale={result['stale']}")

    if result["status"] == "failed":
        raise SystemExit(2)
    if args.strict and result["status"] == "stale":
        raise SystemExit(3)


if __name__ == "__main__":
    main()
