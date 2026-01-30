from __future__ import annotations

import pandas as pd

from src.mlops.data_adapter import align_to_trading_calendar, build_feature_frame, normalize_ohlcv_frame


def test_normalize_ohlcv_frame_maps_columns() -> None:
    df = pd.DataFrame(
        {
            "Date": ["2024-01-01", "2024-01-02"],
            "Open": [10, 11],
            "High": [11, 12],
            "Low": [9, 10],
            "Close": [10, 11],
            "Volume": [100, 110],
        }
    )
    out = normalize_ohlcv_frame(df, timestamp_col="Date")
    assert list(out.columns)[:5] == ["open", "high", "low", "close", "volume"]
    assert isinstance(out.index, pd.DatetimeIndex)
    assert out.loc["2024-01-02", "close"] == 11.0


def test_align_to_trading_calendar_fills() -> None:
    df = pd.DataFrame(
        {
            "timestamp": ["2024-01-02", "2024-01-04"],
            "open": [10, 12],
            "high": [11, 13],
            "low": [9, 11],
            "close": [10, 12],
            "volume": [100, 120],
        }
    )
    norm = normalize_ohlcv_frame(df)
    aligned = align_to_trading_calendar(norm, start="2024-01-02", end="2024-01-04")
    assert "suspended" in aligned.columns
    assert aligned.loc["2024-01-03", "volume"] == 0.0
    assert bool(aligned.loc["2024-01-03", "suspended"]) is True


def test_build_feature_frame_adds_returns() -> None:
    df = pd.DataFrame(
        {
            "timestamp": ["2024-01-01", "2024-01-02"],
            "open": [10, 11],
            "high": [11, 12],
            "low": [9, 10],
            "close": [10, 11],
            "volume": [100, 110],
        }
    )
    norm = normalize_ohlcv_frame(df)
    features = build_feature_frame(norm, window=2)
    assert "return_1d" in features.columns
    assert "vol_2" in features.columns
