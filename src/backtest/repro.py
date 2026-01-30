"""
Reproducibility helpers: snapshot, fingerprints, and report signatures.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import platform
import subprocess
import sys
from typing import Any, Dict, Iterable, Optional

import pandas as pd

try:
    from src import __version__ as _pkg_version
except Exception:  # pragma: no cover - fallback if package init missing
    _pkg_version = "unknown"


def _to_builtin(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _to_builtin(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_builtin(v) for v in value]
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    return value


def compute_data_fingerprint(data_map: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
    """Compute a deterministic fingerprint for data used in a backtest."""
    hasher = hashlib.sha256()
    per_symbol: Dict[str, Any] = {}
    for symbol in sorted(data_map.keys()):
        df = data_map[symbol]
        if df is None or df.empty:
            per_symbol[symbol] = {"rows": 0, "fingerprint": None}
            hasher.update(symbol.encode("utf-8"))
            continue
        frame = df.copy()
        frame.index = pd.to_datetime(frame.index)
        frame = frame.sort_index()
        cols = [c for c in ["open", "high", "low", "close", "volume"] if c in frame.columns]
        if cols:
            frame = frame[cols]
        hash_values = pd.util.hash_pandas_object(frame, index=True).values
        sym_hash = hashlib.sha256(hash_values.tobytes()).hexdigest()
        per_symbol[symbol] = {
            "rows": int(len(frame)),
            "start": str(frame.index.min().date()) if len(frame) else None,
            "end": str(frame.index.max().date()) if len(frame) else None,
            "columns": list(frame.columns),
            "fingerprint": sym_hash,
        }
        hasher.update(symbol.encode("utf-8"))
        hasher.update(sym_hash.encode("utf-8"))
    return {"per_symbol": per_symbol, "combined": hasher.hexdigest()}


def build_repro_command(args: Any, script_name: str = "unified_backtest_framework.py") -> Optional[str]:
    """Build a reproducible CLI command from parsed arguments."""
    if not hasattr(args, "command"):
        return None
    if args.command != "run":
        return None
    tokens = ["python", script_name, "run"]
    tokens.extend(["--strategy", args.strategy])
    tokens.append("--symbols")
    tokens.extend(args.symbols)
    tokens.extend(["--start", args.start, "--end", args.end])
    tokens.extend(["--source", args.source])
    if args.benchmark:
        tokens.extend(["--benchmark", args.benchmark])
    if args.benchmark_source:
        tokens.extend(["--benchmark_source", args.benchmark_source])
    if args.params:
        tokens.extend(["--params", args.params])
    tokens.extend(["--cash", str(args.cash)])
    tokens.extend(["--commission", str(args.commission)])
    tokens.extend(["--slippage", str(args.slippage)])
    if args.adj:
        tokens.extend(["--adj", str(args.adj)])
    if args.out_dir:
        tokens.extend(["--out_dir", str(args.out_dir)])
    if args.cache_dir:
        tokens.extend(["--cache_dir", str(args.cache_dir)])
    if getattr(args, "calendar", None):
        tokens.extend(["--calendar", str(args.calendar)])
    if getattr(args, "plot", False):
        tokens.append("--plot")
    if getattr(args, "fee_config", None):
        tokens.extend(["--fee-config", str(args.fee_config)])
    if getattr(args, "fee_params", None):
        tokens.extend(["--fee-params", str(args.fee_params)])
    return subprocess.list2cmdline(tokens)


def build_snapshot_payload(
    *,
    run_config: Dict[str, Any],
    metrics: Dict[str, Any],
    data_fingerprint: Dict[str, Any],
    quality_report: Optional[Dict[str, Any]] = None,
    repro_command: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the snapshot payload for a single run."""
    payload = {
        "created_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "version": {"package": _pkg_version},
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
        },
        "run_config": run_config,
        "metrics": metrics,
        "data_snapshot": data_fingerprint,
        "quality_report": quality_report,
        "repro_command": repro_command,
    }
    return _to_builtin(payload)


def compute_report_signature(payload: Dict[str, Any]) -> str:
    """Compute SHA256 signature for a report payload."""
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def write_snapshot(report_dir: str, payload: Dict[str, Any], filename: str = "run_snapshot.json") -> str:
    """Write snapshot payload to disk."""
    os.makedirs(report_dir, exist_ok=True)
    path = os.path.join(report_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return path
