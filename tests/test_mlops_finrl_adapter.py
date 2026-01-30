from __future__ import annotations

import pandas as pd

from src.mlops.finrl_adapter import build_finrl_frame


def test_build_finrl_frame() -> None:
    df_a = pd.DataFrame(
        {
            "timestamp": ["2024-01-01", "2024-01-02"],
            "open": [10, 11],
            "high": [11, 12],
            "low": [9, 10],
            "close": [10, 11],
            "volume": [100, 110],
        }
    )
    df_b = pd.DataFrame(
        {
            "timestamp": ["2024-01-01"],
            "open": [20],
            "high": [21],
            "low": [19],
            "close": [20],
            "volume": [200],
        }
    )
    out = build_finrl_frame({"AAA": df_a, "BBB": df_b})
    assert list(out.columns) == ["date", "tic", "open", "high", "low", "close", "volume"]
    assert len(out) == 3
    assert set(out["tic"].unique()) == {"AAA", "BBB"}
