"""
Risk metrics and performance attribution helpers.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd


def compute_var_es(returns: pd.Series, level: float = 0.95) -> Tuple[float, float]:
    """Compute historical VaR/ES at the given confidence level (loss as positive)."""
    if returns is None or returns.empty:
        return float("nan"), float("nan")
    series = returns.dropna().astype(float)
    if series.empty:
        return float("nan"), float("nan")
    quantile = np.nanquantile(series, 1 - level)
    var = -float(quantile)
    tail = series[series <= quantile]
    es = -float(tail.mean()) if not tail.empty else float("nan")
    return var, es


def compute_tracking_error(
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series,
    annual_factor: float = 252.0,
) -> float:
    """Annualized tracking error from active returns."""
    if strategy_returns is None or benchmark_returns is None:
        return float("nan")
    aligned = pd.concat([strategy_returns, benchmark_returns], axis=1).dropna()
    if aligned.empty:
        return float("nan")
    active = aligned.iloc[:, 0] - aligned.iloc[:, 1]
    return float(active.std(ddof=1) * np.sqrt(annual_factor)) if len(active) > 1 else float("nan")


def compute_information_ratio(
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series,
    annual_factor: float = 252.0,
) -> float:
    """Information ratio: active return / tracking error."""
    if strategy_returns is None or benchmark_returns is None:
        return float("nan")
    aligned = pd.concat([strategy_returns, benchmark_returns], axis=1).dropna()
    if aligned.empty:
        return float("nan")
    active = aligned.iloc[:, 0] - aligned.iloc[:, 1]
    tracking = active.std(ddof=1) * np.sqrt(annual_factor) if len(active) > 1 else float("nan")
    if tracking and tracking == tracking and tracking != 0:
        return float(active.mean() * annual_factor / tracking)
    return float("nan")


def compute_capm_metrics(
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series,
    risk_free: float = 0.0,
    annual_factor: float = 252.0,
) -> Dict[str, float]:
    """Compute CAPM beta/alpha/r2 using daily returns."""
    if strategy_returns is None or benchmark_returns is None:
        return {"beta": float("nan"), "alpha_daily": float("nan"), "alpha_annual": float("nan"), "r2": float("nan")}
    aligned = pd.concat([strategy_returns, benchmark_returns], axis=1).dropna()
    if aligned.empty:
        return {"beta": float("nan"), "alpha_daily": float("nan"), "alpha_annual": float("nan"), "r2": float("nan")}
    y = aligned.iloc[:, 0].astype(float) - risk_free / annual_factor
    x = aligned.iloc[:, 1].astype(float) - risk_free / annual_factor
    var_x = float(np.var(x, ddof=1)) if len(x) > 1 else 0.0
    if var_x == 0:
        beta = float("nan")
        alpha_daily = float("nan")
        r2 = float("nan")
    else:
        beta = float(np.cov(y, x, ddof=1)[0, 1] / var_x)
        alpha_daily = float(y.mean() - beta * x.mean())
        y_hat = beta * x + alpha_daily
        ss_res = float(((y - y_hat) ** 2).sum())
        ss_tot = float(((y - y.mean()) ** 2).sum())
        r2 = float(1 - ss_res / ss_tot) if ss_tot != 0 else float("nan")
    alpha_annual = float((1 + alpha_daily) ** annual_factor - 1) if alpha_daily == alpha_daily else float("nan")
    return {"beta": beta, "alpha_daily": alpha_daily, "alpha_annual": alpha_annual, "r2": r2}


def compute_style_exposure(
    strategy_returns: pd.Series,
    benchmark_returns: Optional[pd.Series] = None,
) -> Dict[str, float]:
    """
    Estimate style exposure via correlation with factor proxies.
    """
    if strategy_returns is None:
        return {"market_corr": float("nan"), "momentum_corr": float("nan"), "volatility_corr": float("nan")}
    strategy = strategy_returns.dropna().astype(float)
    if strategy.empty:
        return {"market_corr": float("nan"), "momentum_corr": float("nan"), "volatility_corr": float("nan")}
    market = benchmark_returns.dropna().astype(float) if benchmark_returns is not None else strategy
    momentum = market.rolling(20).sum()
    volatility = market.rolling(20).std(ddof=1)
    aligned = pd.concat([strategy, market, momentum, volatility], axis=1).dropna()
    if aligned.empty:
        return {"market_corr": float("nan"), "momentum_corr": float("nan"), "volatility_corr": float("nan")}
    corr = aligned.corr()
    return {
        "market_corr": float(corr.iloc[0, 1]),
        "momentum_corr": float(corr.iloc[0, 2]),
        "volatility_corr": float(corr.iloc[0, 3]),
    }


def compute_concentration_metrics(weights: Dict[str, float]) -> Dict[str, float]:
    """Compute concentration metrics from position weights."""
    if not weights:
        return {"hhi": float("nan"), "max_weight": float("nan"), "top5_weight": float("nan")}
    series = pd.Series(weights, dtype=float).abs()
    if series.sum() == 0:
        return {"hhi": float("nan"), "max_weight": float("nan"), "top5_weight": float("nan")}
    normalized = series / series.sum()
    hhi = float((normalized ** 2).sum())
    max_weight = float(normalized.max())
    top5_weight = float(normalized.sort_values(ascending=False).head(5).sum())
    return {"hhi": hhi, "max_weight": max_weight, "top5_weight": top5_weight}


def compute_sector_exposure(
    weights: Dict[str, float],
    sector_map: Dict[str, str],
) -> Dict[str, float]:
    """Aggregate weights by sector."""
    if not weights or not sector_map:
        return {}
    sector_totals: Dict[str, float] = {}
    for symbol, weight in weights.items():
        sector = sector_map.get(symbol, "UNKNOWN")
        sector_totals[sector] = sector_totals.get(sector, 0.0) + float(weight)
    total = sum(abs(v) for v in sector_totals.values()) or 1.0
    return {sector: float(value) / total for sector, value in sector_totals.items()}
