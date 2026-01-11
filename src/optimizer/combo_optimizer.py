"""
组合策略权重优化工具

特点：
- 纯 pandas/numpy 实现，无需 backtrader 依赖
- 网格搜索/穷举权重，默认仅少量组合即可出结果
- 输出 Sharpe、CAGR、波动率、最大回撤等指标，并返回最佳权重
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

import numpy as np
import pandas as pd


@dataclass
class PortfolioResult:
    """组合优化结果。"""

    weights: Dict[str, float]
    stats: Dict[str, float]
    nav: pd.Series


def _max_drawdown(nav: pd.Series) -> float:
    """Calculate max drawdown on a NAV series."""
    roll_max = nav.cummax()
    dd = (nav / roll_max - 1.0).fillna(0)
    return float(dd.min())


def _align_returns(nav_map: Mapping[str, pd.Series]) -> pd.DataFrame:
    aligned = pd.concat({k: v for k, v in nav_map.items()}, axis=1).ffill().dropna(how="all")
    # pct_change 第一行设为 0，保持维度一致
    returns = aligned.pct_change().fillna(0.0)
    return returns


def _weight_grid(n: int, step: float, allow_short: bool, max_weight: float) -> Iterable[Tuple[float, ...]]:
    """Generate weight tuples that sum to 1 within tolerance."""
    step = float(step)
    if step <= 0:
        raise ValueError("step must be positive")
    bounds = (-max_weight if allow_short else 0.0, max_weight)
    candidates = np.round(np.arange(bounds[0], bounds[1] + 1e-9, step), 6)
    for weights in itertools.product(candidates, repeat=n):
        total = round(sum(weights), 6)
        if abs(total - 1.0) > step / 2:
            continue
        if not allow_short and any(w < 0 for w in weights):  # pragma: no cover - already excluded by bounds
            continue
        yield weights


def _score(
    weights: Dict[str, float],
    returns: pd.DataFrame,
    risk_free: float = 0.0,
) -> Tuple[pd.Series, Dict[str, float]]:
    w_vec = np.array([weights[k] for k in returns.columns], dtype=float)
    weighted_ret = returns.mul(w_vec, axis=1).sum(axis=1)
    nav = (1 + weighted_ret).cumprod()

    mean = float(weighted_ret.mean())
    vol = float(weighted_ret.std())
    sharpe = (mean - risk_free) / vol if vol > 1e-9 else 0.0
    stats = {
        "cagr": float(nav.iloc[-1] ** (252 / max(len(nav), 1)) - 1),
        "vol": vol,
        "sharpe": sharpe,
        "max_drawdown": _max_drawdown(nav),
    }
    return nav, stats


def optimize_portfolio(
    nav_map: Mapping[str, pd.Series],
    step: float = 0.25,
    objective: str = "sharpe",
    allow_short: bool = False,
    max_weight: float = 1.0,
    risk_free: float = 0.0,
) -> PortfolioResult:
    """
    穷举式权重搜索，返回最佳组合。

    Args:
        nav_map: {name: nav_series}
        step: 权重步长（越小组合越多，耗时增加）
        objective: sharpe/return/drawdown
        allow_short: 是否允许负权重
        max_weight: 单资产权重上限
        risk_free: 风险自由收益（已按日尺度传入）
    """
    if not nav_map:
        raise ValueError("nav_map is empty")
    if step <= 0 or step > 1:
        raise ValueError("step must be in (0, 1]")

    returns = _align_returns(nav_map)
    names = list(nav_map.keys())
    best: PortfolioResult | None = None

    for weights in _weight_grid(len(names), step=step, allow_short=allow_short, max_weight=max_weight):
        weight_dict = {name: float(w) for name, w in zip(names, weights)}
        nav, stats = _score(weight_dict, returns, risk_free=risk_free)

        if best is None:
            best = PortfolioResult(weight_dict, stats, nav)
            continue

        if objective == "sharpe":
            better = stats["sharpe"] > best.stats["sharpe"]
        elif objective == "return":
            better = nav.iloc[-1] > best.nav.iloc[-1]
        elif objective == "drawdown":
            better = stats["max_drawdown"] > best.stats["max_drawdown"]
        else:
            raise ValueError(f"Unknown objective: {objective}")

        if better:
            best = PortfolioResult(weight_dict, stats, nav)

    if best is None:
        raise RuntimeError("No feasible weights found, adjust step or constraints.")  # pragma: no cover
    return best


def load_nav_series(path: str) -> pd.Series:
    """
    读取 NAV CSV 文件，自动寻找 nav/net_value 列。

    允许第一列为日期索引，或无索引时按行号生成。
    """
    df = pd.read_csv(path)
    candidates = [c for c in df.columns if str(c).lower() in ("nav", "net_value", "value", "close")]
    if not candidates:
        raise ValueError(f"No NAV column found in {path}")
    col = candidates[0]
    nav = pd.to_numeric(df[col], errors="coerce").dropna()
    if not isinstance(df.index, pd.DatetimeIndex):
        try:
            nav.index = pd.to_datetime(df.iloc[:, 0])
        except Exception:
            nav.index = pd.RangeIndex(len(nav))
    return nav
