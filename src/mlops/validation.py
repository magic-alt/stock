"""
Validation utilities for AI strategy consistency and drift detection.
"""
from __future__ import annotations

from typing import Dict, Iterable, Tuple

import numpy as np
import pandas as pd


def population_stability_index(
    expected: pd.Series,
    actual: pd.Series,
    *,
    buckets: int = 10,
) -> float:
    """Compute PSI between two distributions."""
    expected = expected.dropna().astype(float)
    actual = actual.dropna().astype(float)
    if expected.empty or actual.empty:
        return 0.0

    quantiles = np.linspace(0, 1, buckets + 1)
    breakpoints = expected.quantile(quantiles).to_numpy(copy=True)
    breakpoints[0] = -np.inf
    breakpoints[-1] = np.inf

    expected_counts = np.histogram(expected, bins=breakpoints)[0]
    actual_counts = np.histogram(actual, bins=breakpoints)[0]

    expected_pct = expected_counts / max(expected_counts.sum(), 1)
    actual_pct = actual_counts / max(actual_counts.sum(), 1)
    eps = 1e-6
    psi = np.sum((expected_pct - actual_pct) * np.log((expected_pct + eps) / (actual_pct + eps)))
    return float(psi)


def detect_feature_drift(
    reference: pd.DataFrame,
    current: pd.DataFrame,
    *,
    threshold: float = 0.2,
) -> Dict[str, object]:
    """Detect feature drift using PSI."""
    results: Dict[str, object] = {"psi": {}, "drifted": []}
    common = [c for c in reference.columns if c in current.columns]
    for col in common:
        if not np.issubdtype(reference[col].dtype, np.number):
            continue
        psi = population_stability_index(reference[col], current[col])
        results["psi"][col] = psi
        if psi >= threshold:
            results["drifted"].append(col)
    results["threshold"] = threshold
    return results


def compare_backtest_live_metrics(
    backtest: Dict[str, float],
    live: Dict[str, float],
    *,
    tolerances: Dict[str, float],
) -> Dict[str, Dict[str, float | bool | None]]:
    """Compare metric deltas between backtest and live runs."""
    results: Dict[str, Dict[str, float | bool | None]] = {}
    for metric, tol in tolerances.items():
        b = backtest.get(metric)
        l = live.get(metric)
        if b is None or l is None:
            results[metric] = {"backtest": b, "live": l, "diff": None, "tolerance": tol, "pass": False}
            continue
        diff = abs(float(b) - float(l))
        results[metric] = {"backtest": b, "live": l, "diff": diff, "tolerance": tol, "pass": diff <= tol}
    results["_passed"] = {"pass": all(v.get("pass") for v in results.values() if isinstance(v, dict))}
    return results
