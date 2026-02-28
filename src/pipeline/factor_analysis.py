"""
Factor Analysis Module

Cross-factor correlation analysis, redundancy detection, and Information
Coefficient (IC) analysis for factor evaluation and selection.
"""
from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


def compute_factor_correlation(factor_df: pd.DataFrame) -> pd.DataFrame:
    """Compute pairwise Pearson correlation between factors.

    Args:
        factor_df: DataFrame where each column is a factor series.

    Returns:
        Correlation matrix (symmetric DataFrame).
    """
    if factor_df.empty:
        return pd.DataFrame()
    return factor_df.corr(method="pearson")


def find_redundant_factors(
    factor_df: pd.DataFrame,
    threshold: float = 0.85,
) -> List[Tuple[str, str, float]]:
    """Identify pairs of factors with absolute correlation above *threshold*.

    Args:
        factor_df: DataFrame of factor values (columns = factor names).
        threshold: Correlation threshold for redundancy.

    Returns:
        List of (factor_a, factor_b, correlation) tuples sorted by |corr| desc.
    """
    if factor_df.empty:
        return []

    corr = factor_df.corr().abs()
    pairs: List[Tuple[str, str, float]] = []
    seen = set()

    for i, col_a in enumerate(corr.columns):
        for j, col_b in enumerate(corr.columns):
            if i >= j:
                continue
            val = corr.iloc[i, j]
            if val >= threshold:
                key = tuple(sorted((col_a, col_b)))
                if key not in seen:
                    seen.add(key)
                    pairs.append((col_a, col_b, float(val)))

    pairs.sort(key=lambda x: x[2], reverse=True)
    return pairs


def factor_ic_analysis(
    factor_df: pd.DataFrame,
    forward_returns: pd.Series,
    method: str = "spearman",
) -> pd.Series:
    """Compute Information Coefficient for each factor.

    IC = rank correlation between factor value and subsequent returns.

    Args:
        factor_df: DataFrame of factor values (columns = factor names).
        forward_returns: Series of forward returns aligned with factor_df index.
        method: Correlation method ("spearman" or "pearson").

    Returns:
        Series of IC values indexed by factor name.
    """
    if factor_df.empty or forward_returns.empty:
        return pd.Series(dtype=float)

    aligned = factor_df.align(forward_returns, join="inner", axis=0)
    factors_aligned = aligned[0]
    returns_aligned = aligned[1]

    if factors_aligned.empty:
        return pd.Series(dtype=float)

    ic_values: Dict[str, float] = {}
    for col in factors_aligned.columns:
        mask = factors_aligned[col].notna() & returns_aligned.notna()
        if mask.sum() < 5:
            ic_values[col] = np.nan
            continue
        ic_values[col] = float(
            factors_aligned.loc[mask, col].corr(returns_aligned[mask], method=method)
        )

    return pd.Series(ic_values, name="IC")


def factor_ic_by_period(
    factor_df: pd.DataFrame,
    forward_returns: pd.Series,
    method: str = "spearman",
) -> pd.DataFrame:
    """Compute rolling IC by each time period (row) for each factor.

    Useful for evaluating factor stability over time. Groups by the DataFrame
    index (assumed to be dates) and computes cross-sectional IC at each date.

    Args:
        factor_df: DataFrame with MultiIndex (date, symbol) or single-level date index.
        forward_returns: Matching return series.
        method: Correlation method.

    Returns:
        DataFrame (index=dates, columns=factor names) of per-period IC values.
    """
    if factor_df.empty or forward_returns.empty:
        return pd.DataFrame()

    aligned = factor_df.align(forward_returns, join="inner", axis=0)
    fdf = aligned[0]
    ret = aligned[1]

    # If MultiIndex, group by the first level (date)
    if isinstance(fdf.index, pd.MultiIndex):
        groups = fdf.groupby(level=0)
    else:
        # Single-level: each row is one period, cross-sectional IC not meaningful
        # Return overall IC as single-row result
        ic = factor_ic_analysis(fdf, ret, method=method)
        return pd.DataFrame([ic])

    records = []
    for dt, grp in groups:
        ret_slice = ret.loc[grp.index]
        row: Dict[str, float] = {}
        for col in grp.columns:
            mask = grp[col].notna() & ret_slice.notna()
            if mask.sum() < 3:
                row[col] = np.nan
            else:
                row[col] = float(grp.loc[mask, col].corr(ret_slice[mask], method=method))
        records.append((dt, row))

    if not records:
        return pd.DataFrame()

    return pd.DataFrame.from_records(
        [r[1] for r in records],
        index=[r[0] for r in records],
    )


def factor_summary(factor_df: pd.DataFrame) -> pd.DataFrame:
    """Compute descriptive statistics for each factor.

    Returns:
        DataFrame with count, mean, std, min, max, skew, kurtosis per factor.
    """
    if factor_df.empty:
        return pd.DataFrame()

    stats = factor_df.describe().T
    stats["skew"] = factor_df.skew()
    stats["kurtosis"] = factor_df.kurtosis()
    stats["missing_pct"] = (factor_df.isna().sum() / len(factor_df) * 100).round(2)
    return stats
