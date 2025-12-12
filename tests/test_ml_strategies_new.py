import pandas as pd
import numpy as np

from src.strategies.ml_strategies import (
    DeepSequenceStrategy,
    ReinforcementLearningSignalStrategy,
    FeatureSelectionStrategy,
    EnsembleVotingStrategy,
)


def _dummy_df(rows: int = 120) -> pd.DataFrame:
    idx = pd.date_range("2023-01-01", periods=rows, freq="D")
    base = np.linspace(100, 120, rows) + np.random.normal(0, 1, rows)
    return pd.DataFrame(
        {
            "开盘": base + np.random.normal(0, 0.5, rows),
            "最高": base + np.random.uniform(0.5, 1.5, rows),
            "最低": base - np.random.uniform(0.5, 1.5, rows),
            "收盘": base + np.random.normal(0, 0.5, rows),
            "成交量": np.random.randint(1_000_000, 2_000_000, rows),
        },
        index=idx,
    )


def test_deep_sequence_strategy_outputs_signal_and_prob():
    df = _dummy_df()
    strat = DeepSequenceStrategy(arch="lstm", lookback=30, threshold=0.52)
    res = strat.generate_signals(df)
    assert not res.empty
    assert set(["signal", "prob"]).issubset(res.columns)
    assert res["signal"].iloc[-1] in (-1, 0, 1)


def test_rl_strategy_generates_actions():
    df = _dummy_df()
    strat = ReinforcementLearningSignalStrategy(epsilon=0.0, lookback=15)
    res = strat.generate_signals(df)
    assert not res.empty
    assert res["signal"].isin([-1, 0, 1]).all()


def test_feature_selection_and_ensemble():
    df = _dummy_df()
    selector = FeatureSelectionStrategy(top_k=5)
    res_sel = selector.generate_signals(df)
    assert selector.selected_features  # ensure features picked
    assert "signal" in res_sel

    dl = DeepSequenceStrategy(arch="transformer", lookback=20)
    rl = ReinforcementLearningSignalStrategy(epsilon=0.2, lookback=10)
    ensemble = EnsembleVotingStrategy([selector, dl, rl], vote="prob_mean")
    res = ensemble.generate_signals(df)
    assert not res.empty
    assert "prob" in res
    assert res["signal"].isin([-1, 0, 1]).any()
