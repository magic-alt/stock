"""
Qlib data adapter helpers.
"""
from __future__ import annotations

from typing import Dict, Literal

import pandas as pd

from .data_adapter import normalize_ohlcv_frame

FormatType = Literal["long", "multiindex"]


def build_qlib_frame(
    data_map: Dict[str, pd.DataFrame],
    *,
    format_type: FormatType = "multiindex",
    datetime_col: str = "datetime",
    instrument_col: str = "instrument",
    use_qlib_field_prefix: bool = False,
) -> pd.DataFrame:
    """
    Build a Qlib-style DataFrame.

    - format_type="long": columns [datetime, instrument, open, high, low, close, volume]
    - format_type="multiindex": MultiIndex (datetime, instrument) with OHLCV columns
    """
    frames = []
    for symbol, df in data_map.items():
        if df is None or df.empty:
            continue
        norm = normalize_ohlcv_frame(df)
        out = norm.reset_index()
        if datetime_col not in out.columns:
            if "timestamp" in out.columns:
                out = out.rename(columns={"timestamp": datetime_col})
            elif "index" in out.columns:
                out = out.rename(columns={"index": datetime_col})
        out[datetime_col] = pd.to_datetime(out[datetime_col])
        out[instrument_col] = symbol
        columns = ["open", "high", "low", "close", "volume"]
        if use_qlib_field_prefix:
            rename_map = {col: f"${col}" for col in columns}
            out = out.rename(columns=rename_map)
            columns = [rename_map[col] for col in columns]
        frames.append(out[[datetime_col, instrument_col] + columns])

    if not frames:
        return pd.DataFrame()
    merged = pd.concat(frames, ignore_index=True)
    merged = merged.sort_values([datetime_col, instrument_col])
    if format_type == "long":
        return merged.reset_index(drop=True)
    return merged.set_index([datetime_col, instrument_col]).sort_index()
