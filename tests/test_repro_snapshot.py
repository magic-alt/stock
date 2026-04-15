import pandas as pd

from src.backtest.repro import (
    build_snapshot_payload,
    compute_data_fingerprint,
    compute_report_signature,
)


def test_snapshot_signature_stable():
    dates = pd.to_datetime(["2024-01-01", "2024-01-02"])
    df = pd.DataFrame(
        {
            "open": [10.0, 10.5],
            "high": [10.6, 11.0],
            "low": [9.8, 10.2],
            "close": [10.3, 10.8],
            "volume": [100, 110],
        },
        index=dates,
    )
    fingerprint = compute_data_fingerprint({"AAA": df})
    payload = build_snapshot_payload(
        run_config={"strategy": "sma", "symbols": ["AAA"]},
        metrics={"cum_return": 0.1, "sharpe": 1.2},
        data_fingerprint=fingerprint,
        quality_report={"summary": {"symbols": 1}},
        repro_command="python unified_backtest_framework.py run --strategy sma",
    )
    sig1 = compute_report_signature(payload)
    sig2 = compute_report_signature(payload)
    assert sig1 == sig2


def test_snapshot_payload_normalizes_non_finite_numbers():
    dates = pd.to_datetime(["2024-01-01", "2024-01-02"])
    df = pd.DataFrame(
        {
            "open": [10.0, 10.5],
            "high": [10.6, 11.0],
            "low": [9.8, 10.2],
            "close": [10.3, 10.8],
            "volume": [100, 110],
        },
        index=dates,
    )
    fingerprint = compute_data_fingerprint({"AAA": df})
    payload = build_snapshot_payload(
        run_config={"strategy": "sma", "symbols": ["AAA"]},
        metrics={"cum_return": float("nan"), "sharpe": float("inf")},
        data_fingerprint=fingerprint,
        quality_report={"summary": {"symbols": 1}},
        repro_command="python unified_backtest_framework.py run --strategy sma",
    )

    assert payload["metrics"]["cum_return"] is None
    assert payload["metrics"]["sharpe"] is None
