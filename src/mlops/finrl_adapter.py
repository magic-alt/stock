"""
FinRL data adapter helpers.
"""
from __future__ import annotations

from typing import Dict

import pandas as pd

from .data_adapter import normalize_ohlcv_frame


def build_finrl_frame(
    data_map: Dict[str, pd.DataFrame],
    *,
    date_col: str = "date",
    symbol_col: str = "tic",
) -> pd.DataFrame:
    """
    Build a FinRL-style long DataFrame with columns:
    [date, tic, open, high, low, close, volume].
    """
    frames = []
    for symbol, df in data_map.items():
        if df is None or df.empty:
            continue
        norm = normalize_ohlcv_frame(df)
        out = norm.reset_index()
        if date_col not in out.columns:
            if "timestamp" in out.columns:
                out = out.rename(columns={"timestamp": date_col})
            elif "index" in out.columns:
                out = out.rename(columns={"index": date_col})
        out[date_col] = pd.to_datetime(out[date_col])
        out[symbol_col] = symbol
        frames.append(out[[date_col, symbol_col, "open", "high", "low", "close", "volume"]])
    if not frames:
        return pd.DataFrame(columns=[date_col, symbol_col, "open", "high", "low", "close", "volume"])
    merged = pd.concat(frames, ignore_index=True)
    return merged.sort_values([date_col, symbol_col]).reset_index(drop=True)
