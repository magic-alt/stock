"""
Data quality checks and reporting utilities.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import pandas as pd

from .trading_calendar import TradingCalendar, infer_missing_sessions


@dataclass
class QualitySummary:
    """Summary metrics for a single symbol."""
    symbol: str
    rows: int
    start: Optional[str]
    end: Optional[str]
    missing_sessions: int
    missing_ratio: float
    duplicate_rows: int
    nan_rows: int
    ohlc_anomalies: int
    negative_prices: int
    zero_volume_ratio: float
    outlier_returns: int
    max_missing_streak: int


def _max_gap(missing: pd.DatetimeIndex) -> int:
    if missing.empty:
        return 0
    missing = missing.sort_values()
    gaps = 1
    best = 1
    prev = missing[0]
    for cur in missing[1:]:
        if (cur - prev).days <= 1:
            gaps += 1
        else:
            best = max(best, gaps)
            gaps = 1
        prev = cur
    return max(best, gaps)


def _ensure_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in ["open", "high", "low", "close", "volume"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def run_quality_checks(
    data_map: Dict[str, pd.DataFrame],
    *,
    start: str,
    end: str,
    calendar: Optional[TradingCalendar] = None,
    price_jump_threshold: float = 0.2,
) -> Dict[str, object]:
    """
    Run data quality checks for a set of symbol dataframes.
    """
    calendar = calendar or TradingCalendar()
    sessions = calendar.sessions(start, end)
    per_symbol: Dict[str, Dict[str, object]] = {}
    summaries: Dict[str, QualitySummary] = {}

    for symbol, df in (data_map or {}).items():
        if df is None or df.empty:
            per_symbol[symbol] = {"error": "empty"}
            summaries[symbol] = QualitySummary(
                symbol=symbol,
                rows=0,
                start=None,
                end=None,
                missing_sessions=len(sessions),
                missing_ratio=1.0 if len(sessions) else 0.0,
                duplicate_rows=0,
                nan_rows=0,
                ohlc_anomalies=0,
                negative_prices=0,
                zero_volume_ratio=0.0,
                outlier_returns=0,
                max_missing_streak=len(sessions),
            )
            continue

        frame = _ensure_ohlc(df)
        idx = pd.to_datetime(frame.index)
        if idx.tz is not None:
            idx = idx.tz_localize(None)
        idx = idx.normalize()
        frame = frame.copy()
        frame.index = idx
        frame = frame.sort_index()

        missing = infer_missing_sessions(frame.index, sessions)
        duplicate_rows = int(frame.index.duplicated().sum())
        nan_rows = int(frame[["open", "high", "low", "close"]].isna().any(axis=1).sum())

        ohlc_anomalies = 0
        if {"open", "high", "low", "close"}.issubset(frame.columns):
            ohlc_anomalies = int(((frame["high"] < frame["low"]) |
                                  (frame["open"] > frame["high"]) |
                                  (frame["open"] < frame["low"]) |
                                  (frame["close"] > frame["high"]) |
                                  (frame["close"] < frame["low"])).sum())

        negative_prices = 0
        if {"open", "high", "low", "close"}.issubset(frame.columns):
            negative_prices = int(((frame[["open", "high", "low", "close"]] <= 0).any(axis=1)).sum())

        zero_volume_ratio = 0.0
        if "volume" in frame.columns and len(frame) > 0:
            zero_volume_ratio = float((frame["volume"] == 0).mean())

        outlier_returns = 0
        if "close" in frame.columns:
            returns = frame["close"].pct_change()
            outlier_returns = int((returns.abs() > price_jump_threshold).sum())

        summary = QualitySummary(
            symbol=symbol,
            rows=len(frame),
            start=str(frame.index.min().date()) if len(frame) else None,
            end=str(frame.index.max().date()) if len(frame) else None,
            missing_sessions=len(missing),
            missing_ratio=float(len(missing) / len(sessions)) if len(sessions) else 0.0,
            duplicate_rows=duplicate_rows,
            nan_rows=nan_rows,
            ohlc_anomalies=ohlc_anomalies,
            negative_prices=negative_prices,
            zero_volume_ratio=zero_volume_ratio,
            outlier_returns=outlier_returns,
            max_missing_streak=_max_gap(missing),
        )

        per_symbol[symbol] = {
            "rows": summary.rows,
            "start": summary.start,
            "end": summary.end,
            "missing_sessions": summary.missing_sessions,
            "missing_ratio": summary.missing_ratio,
            "duplicate_rows": summary.duplicate_rows,
            "nan_rows": summary.nan_rows,
            "ohlc_anomalies": summary.ohlc_anomalies,
            "negative_prices": summary.negative_prices,
            "zero_volume_ratio": summary.zero_volume_ratio,
            "outlier_returns": summary.outlier_returns,
            "max_missing_streak": summary.max_missing_streak,
        }
        summaries[symbol] = summary

    summary_rows = list(per_symbol.values())
    overall = {
        "symbols": len(per_symbol),
        "total_rows": int(sum(v.get("rows", 0) for v in per_symbol.values())),
        "total_missing_sessions": int(sum(v.get("missing_sessions", 0) for v in per_symbol.values())),
        "avg_missing_ratio": float(
            sum(v.get("missing_ratio", 0.0) for v in per_symbol.values()) / max(1, len(per_symbol))
        ),
    }

    return {
        "summary": overall,
        "per_symbol": per_symbol,
    }


def save_quality_report(report_dir: str, report: Dict[str, object]) -> Dict[str, str]:
    """Save quality report as JSON and Markdown."""
    import os
    import json

    os.makedirs(report_dir, exist_ok=True)
    json_path = os.path.join(report_dir, "data_quality.json")
    md_path = os.path.join(report_dir, "data_quality.md")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    lines = [
        "# 数据质量报告",
        "",
        "## 总览",
        "",
        f"- symbols: {report.get('summary', {}).get('symbols', 0)}",
        f"- total_rows: {report.get('summary', {}).get('total_rows', 0)}",
        f"- total_missing_sessions: {report.get('summary', {}).get('total_missing_sessions', 0)}",
        f"- avg_missing_ratio: {report.get('summary', {}).get('avg_missing_ratio', 0.0):.2%}",
        "",
        "## 明细",
        "",
        "| Symbol | Rows | Start | End | Missing | Missing% | Duplicates | NaN Rows | OHLC Anom | Neg Price | Zero Vol% | Outlier R | Max Gap |",
        "|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    per_symbol = report.get("per_symbol", {})
    for symbol, info in per_symbol.items():
        lines.append(
            f"| {symbol} | {info.get('rows', 0)} | {info.get('start', '-') or '-'} | {info.get('end', '-') or '-'} | "
            f"{info.get('missing_sessions', 0)} | {info.get('missing_ratio', 0.0):.2%} | "
            f"{info.get('duplicate_rows', 0)} | {info.get('nan_rows', 0)} | "
            f"{info.get('ohlc_anomalies', 0)} | {info.get('negative_prices', 0)} | "
            f"{info.get('zero_volume_ratio', 0.0):.2%} | {info.get('outlier_returns', 0)} | "
            f"{info.get('max_missing_streak', 0)} |"
        )

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return {"json": json_path, "markdown": md_path}
