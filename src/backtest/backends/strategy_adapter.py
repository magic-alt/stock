"""Strategy adapter layer for non-backtrader engines.

Backtrader strategies are class-based and event-driven. Other engines such as
**zipline** prefer a signal/weights-driven workflow. This module provides:

- :class:`SignalAdapter` — a thin protocol describing how a strategy turns
  historical OHLCV frames into a per-date, per-symbol target weight.
- A process-wide registry so strategies can opt into the zipline backend by
  registering a ``compute_signals(data_map, params) -> DataFrame`` function.

The same adapter is reused by :mod:`src.backtest.backends.zipline_backend`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

import numpy as np
import pandas as pd

SignalFn = Callable[[Dict[str, pd.DataFrame], Dict[str, Any]], pd.DataFrame]


@dataclass
class SignalAdapter:
    """Wraps a ``compute_signals`` function for one strategy.

    ``compute_signals(data_map, params)`` must return a wide DataFrame indexed
    by trading date with one column per symbol. Values are target weights in
    [-1, 1] where 1.0 means "100% long this symbol" and 0.0 means "flat".
    Weights are renormalised by the consumer to respect leverage limits.
    """

    name: str
    compute_signals: SignalFn
    description: str = ""


_REGISTRY: Dict[str, SignalAdapter] = {}


def register_adapter(adapter: SignalAdapter) -> None:
    _REGISTRY[adapter.name.lower()] = adapter


def get_adapter(name: str) -> Optional[SignalAdapter]:
    return _REGISTRY.get((name or "").lower())


def available_adapters() -> tuple:
    return tuple(sorted(_REGISTRY))


# ---------------------------------------------------------------------------
# Built-in fallback adapters
# ---------------------------------------------------------------------------


def _buy_and_hold(data_map: Dict[str, pd.DataFrame], params: Dict[str, Any]) -> pd.DataFrame:
    """Equal-weight, always-long fallback for strategies without an adapter."""
    if not data_map:
        return pd.DataFrame()
    union_index = sorted({ts for df in data_map.values() for ts in df.index})
    n = len(data_map)
    weight = 1.0 / max(1, n)
    return pd.DataFrame(
        weight, index=pd.DatetimeIndex(union_index), columns=sorted(data_map.keys())
    )


def _ma_cross(data_map: Dict[str, pd.DataFrame], params: Dict[str, Any]) -> pd.DataFrame:
    """Reference adapter — long when fast MA > slow MA, flat otherwise."""
    fast = int(params.get("fast", 5))
    slow = int(params.get("slow", 20))
    cols = sorted(data_map.keys())
    union_index = sorted({ts for df in data_map.values() for ts in df.index})
    out = pd.DataFrame(0.0, index=pd.DatetimeIndex(union_index), columns=cols)
    for sym, df in data_map.items():
        close = df["close"].astype(float)
        f = close.rolling(fast, min_periods=1).mean()
        s = close.rolling(slow, min_periods=1).mean()
        signal = (f > s).astype(float)
        out[sym] = signal.reindex(out.index).fillna(0.0)
    # Equal weight across active longs each day.
    active = (out > 0).sum(axis=1).replace(0, np.nan)
    out = out.div(active, axis=0).fillna(0.0)
    return out


register_adapter(SignalAdapter("buy_and_hold", _buy_and_hold, "Equal-weight long-only baseline"))
register_adapter(SignalAdapter("ma_cross", _ma_cross, "Fast/slow moving-average crossover"))


def signals_to_orders(
    weights: pd.DataFrame,
    *,
    leverage: float = 1.0,
) -> pd.DataFrame:
    """Clip and renormalise a weight matrix so the gross exposure ≤ ``leverage``."""
    if weights.empty:
        return weights
    clipped = weights.clip(lower=-1.0, upper=1.0)
    gross = clipped.abs().sum(axis=1)
    scale = (leverage / gross.replace(0, np.nan)).clip(upper=1.0).fillna(1.0)
    return clipped.mul(scale, axis=0).fillna(0.0)
