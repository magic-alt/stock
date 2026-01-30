from __future__ import annotations

import pandas as pd

from src.mlops.qlib_adapter import build_qlib_frame


def test_build_qlib_frame_multiindex() -> None:
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
    out = build_qlib_frame({"AAA": df}, format_type="multiindex")
    assert isinstance(out.index, pd.MultiIndex)
    assert out.index.names == ["datetime", "instrument"]
    assert "close" in out.columns


def test_build_qlib_frame_long_with_prefix() -> None:
    df = pd.DataFrame(
        {
            "timestamp": ["2024-01-01"],
            "open": [20],
            "high": [21],
            "low": [19],
            "close": [20],
            "volume": [200],
        }
    )
    out = build_qlib_frame({"BBB": df}, format_type="long", use_qlib_field_prefix=True)
    assert "$close" in out.columns
    assert out.loc[0, "instrument"] == "BBB"
