from __future__ import annotations

import numpy as np
import pandas as pd

from src.mlops.validation import compare_backtest_live_metrics, detect_feature_drift, population_stability_index


def test_population_stability_index_positive() -> None:
    expected = pd.Series(np.random.normal(0, 1, size=500))
    actual = pd.Series(np.random.normal(1.5, 1, size=500))
    psi = population_stability_index(expected, actual)
    assert psi > 0


def test_detect_feature_drift_flags_column() -> None:
    ref = pd.DataFrame({"feature": np.random.normal(0, 1, size=300)})
    cur = pd.DataFrame({"feature": np.random.normal(2, 1, size=300)})
    result = detect_feature_drift(ref, cur, threshold=0.1)
    assert "feature" in result["drifted"]


def test_compare_backtest_live_metrics() -> None:
    backtest = {"sharpe": 1.2, "max_drawdown": 0.1}
    live = {"sharpe": 1.1, "max_drawdown": 0.12}
    result = compare_backtest_live_metrics(backtest, live, tolerances={"sharpe": 0.2, "max_drawdown": 0.05})
    assert result["sharpe"]["pass"] is True
    assert result["_passed"]["pass"] is True
