"""
Vectorized computation layer (V5.0-B-3).

Provides NumPy/Numba-accelerated computation for backtest metrics,
signal generation, and portfolio analytics. Replaces scalar Python loops
with vectorized operations for 5-10x performance improvement.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from numba import njit, prange  # type: ignore[import-untyped]
    HAS_NUMBA = True
except ImportError:
    HAS_NUMBA = False

    # Fallback decorators when numba is not available
    def njit(*args: Any, **kwargs: Any) -> Any:  # type: ignore[misc]
        def decorator(fn: Any) -> Any:
            return fn
        if len(args) == 1 and callable(args[0]):
            return args[0]
        return decorator

    prange = range  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Fast metrics (Numba-accelerated when available)
# ---------------------------------------------------------------------------

@njit(cache=True)
def _sharpe_ratio_fast(returns: np.ndarray, risk_free: float = 0.0, ann_factor: float = 252.0) -> float:
    """Compute annualized Sharpe ratio using vectorized numpy."""
    n = len(returns)
    if n < 2:
        return 0.0
    excess = returns - risk_free / ann_factor
    mean_r = 0.0
    for i in range(n):
        mean_r += excess[i]
    mean_r /= n
    var = 0.0
    for i in range(n):
        diff = excess[i] - mean_r
        var += diff * diff
    var /= (n - 1)
    std = math.sqrt(var) if var > 0 else 0.0
    if std == 0.0:
        return 0.0
    return mean_r / std * math.sqrt(ann_factor)


@njit(cache=True)
def _max_drawdown_fast(nav: np.ndarray) -> float:
    """Compute maximum drawdown from NAV array."""
    n = len(nav)
    if n < 2:
        return 0.0
    peak = nav[0]
    max_dd = 0.0
    for i in range(1, n):
        if nav[i] > peak:
            peak = nav[i]
        dd = (peak - nav[i]) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
    return max_dd


@njit(cache=True)
def _sortino_ratio_fast(returns: np.ndarray, risk_free: float = 0.0, ann_factor: float = 252.0) -> float:
    """Compute Sortino ratio (downside deviation only)."""
    n = len(returns)
    if n < 2:
        return 0.0
    target = risk_free / ann_factor
    mean_excess = 0.0
    for i in range(n):
        mean_excess += returns[i] - target
    mean_excess /= n

    downside_var = 0.0
    count = 0
    for i in range(n):
        diff = returns[i] - target
        if diff < 0:
            downside_var += diff * diff
            count += 1
    if count == 0:
        return 0.0
    downside_std = math.sqrt(downside_var / count)
    if downside_std == 0.0:
        return 0.0
    return mean_excess / downside_std * math.sqrt(ann_factor)


@njit(cache=True)
def _calmar_ratio_fast(nav: np.ndarray, ann_factor: float = 252.0) -> float:
    """Compute Calmar ratio = annualized return / max drawdown."""
    n = len(nav)
    if n < 2 or nav[0] <= 0:
        return 0.0
    total_return = nav[-1] / nav[0] - 1.0
    years = n / ann_factor
    if years <= 0:
        return 0.0
    ann_return = (1.0 + total_return) ** (1.0 / years) - 1.0
    mdd = _max_drawdown_fast(nav)
    if mdd <= 0:
        return 0.0
    return ann_return / mdd


@njit(cache=True)
def _rolling_volatility(returns: np.ndarray, window: int = 20) -> np.ndarray:
    """Compute rolling annualized volatility."""
    n = len(returns)
    result = np.full(n, np.nan)
    for i in range(window - 1, n):
        segment = returns[i - window + 1: i + 1]
        mean_val = 0.0
        for j in range(window):
            mean_val += segment[j]
        mean_val /= window
        var_val = 0.0
        for j in range(window):
            diff = segment[j] - mean_val
            var_val += diff * diff
        var_val /= (window - 1)
        result[i] = math.sqrt(var_val) * math.sqrt(252.0)
    return result


@njit(cache=True)
def _drawdown_series(nav: np.ndarray) -> np.ndarray:
    """Compute drawdown at each point."""
    n = len(nav)
    result = np.zeros(n)
    peak = nav[0]
    for i in range(n):
        if nav[i] > peak:
            peak = nav[i]
        result[i] = (nav[i] - peak) / peak if peak > 0 else 0.0
    return result


# ---------------------------------------------------------------------------
# Public vectorized API
# ---------------------------------------------------------------------------

def compute_metrics_fast(
    nav: np.ndarray,
    risk_free: float = 0.0,
    ann_factor: float = 252.0,
) -> Dict[str, float]:
    """Compute a full set of performance metrics using vectorized operations.

    Args:
        nav: NAV array (absolute values, not returns).
        risk_free: Annual risk-free rate.
        ann_factor: Trading days per year.

    Returns:
        Dict with: cum_return, ann_return, ann_vol, sharpe, sortino,
                   mdd, calmar, skewness, kurtosis.
    """
    nav = np.asarray(nav, dtype=np.float64)
    n = len(nav)
    if n < 2:
        return {k: float("nan") for k in [
            "cum_return", "ann_return", "ann_vol", "sharpe", "sortino",
            "mdd", "calmar", "skewness", "kurtosis",
        ]}

    returns = np.diff(nav) / nav[:-1]
    returns = returns[np.isfinite(returns)]

    cum_return = float(nav[-1] / nav[0] - 1.0) if nav[0] > 0 else float("nan")
    years = n / ann_factor
    ann_return = float((1.0 + cum_return) ** (1.0 / years) - 1.0) if years > 0 else float("nan")
    ann_vol = float(np.std(returns, ddof=1) * np.sqrt(ann_factor)) if len(returns) > 1 else float("nan")
    sharpe = float(_sharpe_ratio_fast(returns, risk_free, ann_factor))
    sortino = float(_sortino_ratio_fast(returns, risk_free, ann_factor))
    mdd = float(_max_drawdown_fast(nav))
    calmar = float(_calmar_ratio_fast(nav, ann_factor))

    # Higher moments
    if len(returns) > 2:
        mean_r = np.mean(returns)
        std_r = np.std(returns, ddof=1)
        if std_r > 0:
            skew = float(np.mean(((returns - mean_r) / std_r) ** 3))
            kurt = float(np.mean(((returns - mean_r) / std_r) ** 4) - 3.0)
        else:
            skew = kurt = 0.0
    else:
        skew = kurt = float("nan")

    return {
        "cum_return": cum_return,
        "ann_return": ann_return,
        "ann_vol": ann_vol,
        "sharpe": sharpe,
        "sortino": sortino,
        "mdd": mdd,
        "calmar": calmar,
        "skewness": skew,
        "kurtosis": kurt,
    }


def compute_var_es_fast(
    returns: np.ndarray,
    confidence: float = 0.95,
) -> Tuple[float, float]:
    """Compute Value-at-Risk and Expected Shortfall (CVaR) using numpy.

    Args:
        returns: Array of returns.
        confidence: Confidence level (e.g. 0.95, 0.99).

    Returns:
        (VaR, ES) tuple — both as negative numbers for losses.
    """
    returns = np.asarray(returns, dtype=np.float64)
    returns = returns[np.isfinite(returns)]
    if len(returns) < 10:
        return (float("nan"), float("nan"))
    sorted_returns = np.sort(returns)
    cutoff = int(len(sorted_returns) * (1 - confidence))
    cutoff = max(cutoff, 1)
    var = float(sorted_returns[cutoff])
    es = float(np.mean(sorted_returns[:cutoff]))
    return (var, es)


def rolling_volatility(series: pd.Series, window: int = 20) -> pd.Series:
    """Compute rolling annualized volatility on a pandas Series."""
    returns = series.pct_change().dropna().values.astype(np.float64)
    vol = _rolling_volatility(returns, window)
    # Align with original index (shifted by 1 due to pct_change)
    idx = series.index[1:]
    return pd.Series(vol, index=idx, name="rolling_vol")


def drawdown_series(nav: pd.Series) -> pd.Series:
    """Compute drawdown series from NAV."""
    dd = _drawdown_series(nav.values.astype(np.float64))
    return pd.Series(dd, index=nav.index, name="drawdown")
