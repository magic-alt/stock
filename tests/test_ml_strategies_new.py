import numpy as np
import pandas as pd
import pytest
import types

from src.strategies.ml_strategies import (
    DeepSequenceStrategy,
    MLWalkForwardStrategy,
    ReinforcementLearningSignalStrategy,
    FeatureSelectionStrategy,
    EnsembleVotingStrategy,
    RegimeAdaptiveMLStrategy,
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


def _dummy_df_en(rows: int = 120) -> pd.DataFrame:
    idx = pd.date_range("2023-01-01", periods=rows, freq="D")
    base = np.linspace(100, 120, rows) + np.random.normal(0, 1, rows)
    return pd.DataFrame(
        {
            "open": base + np.random.normal(0, 0.5, rows),
            "high": base + np.random.uniform(0.5, 1.5, rows),
            "low": base - np.random.uniform(0.5, 1.5, rows),
            "close": base + np.random.normal(0, 0.5, rows),
            "volume": np.random.randint(1_000_000, 2_000_000, rows),
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


def test_regime_adaptive_filters_high_vol():
    df = _dummy_df()
    strat = RegimeAdaptiveMLStrategy(regime_window=10, prob_floor=0.4, prob_cap=0.6)
    res = strat.generate_signals(df)
    assert {"signal", "prob", "regime_vol"} <= set(res.columns)
    # 在震荡期，概率被压回 0.5，信号为0
    noisy_idx = res["regime_vol"].idxmax()
    assert res.loc[noisy_idx, "prob"] == 0.5


def test_ml_walkforward_insufficient_data_returns_zero_signal():
    df = _dummy_df(rows=40)
    strat = MLWalkForwardStrategy(min_train=120, model="auto")
    res = strat.generate_signals(df)
    assert "Signal" in res
    assert res["Signal"].eq(0).all()


def test_ml_walkforward_model_none_returns_zero_signal(monkeypatch):
    df = _dummy_df(rows=80)
    strat = MLWalkForwardStrategy(min_train=20, model="auto")
    monkeypatch.setattr(strat, "_make_model", lambda: None)
    res = strat.generate_signals(df)
    assert "Signal" in res
    assert res["Signal"].eq(0).all()


def test_ml_walkforward_dummy_model_generates_signals():
    df = _dummy_df(rows=80)

    class DummyModel:
        def fit(self, X, y):
            return self

        def predict_proba(self, X):
            return np.tile([0.3, 0.7], (len(X), 1))

    strat = MLWalkForwardStrategy(
        min_train=10,
        prob_long=0.6,
        prob_short=0.6,
        allow_short=True,
        use_regime_ma=0,
    )
    strat._make_model = lambda: DummyModel()
    res = strat.generate_signals(df)
    assert "ML_Prob" in res
    assert res["ML_Prob"].iloc[15] == pytest.approx(0.7)
    assert res["Signal"].abs().sum() > 0


def test_ml_walkforward_ta_accepts_english_columns():
    df = _dummy_df_en(rows=40)
    feats = MLWalkForwardStrategy._ta(df)
    assert {"ret1", "macd", "boll_z", "v_ratio"} <= set(feats.columns)


def test_ml_walkforward_partial_fit_path():
    df = _dummy_df(rows=80)

    class DummyPartialModel:
        def __init__(self):
            self.calls = 0

        def partial_fit(self, X, y, classes=None):
            self.calls += 1
            return self

        def predict_proba(self, X):
            return np.tile([0.4, 0.6], (len(X), 1))

    model = DummyPartialModel()
    strat = MLWalkForwardStrategy(min_train=10, use_partial_fit=True, use_regime_ma=0)
    strat._make_model = lambda: model
    res = strat.generate_signals(df)
    assert model.calls > 0
    assert res["ML_Prob"].iloc[15] == pytest.approx(0.6)


def test_ml_walkforward_decision_function_path_and_regime():
    df = _dummy_df(rows=80)

    class DummyDecisionModel:
        def fit(self, X, y):
            return self

        def decision_function(self, X):
            return np.full(len(X), 1.0)

    strat = MLWalkForwardStrategy(min_train=10, use_regime_ma=5, allow_short=False)
    strat._make_model = lambda: DummyDecisionModel()
    res = strat.generate_signals(df)
    assert res["Signal"].abs().sum() > 0


def test_ml_walkforward_torch_helpers():
    torch = pytest.importorskip("torch")
    strat = MLWalkForwardStrategy(min_train=5, model="mlp")
    X_train = np.random.normal(0, 1, (6, 3))
    y_train = np.array([0, 1, 0, 1, 0, 1])

    def model_ctor(d):
        return torch.nn.Linear(d, 1)

    net = strat._torch_fit(model_ctor, X_train, y_train)
    prob = strat._torch_predict(net, np.random.normal(0, 1, (1, 3)))
    assert 0.0 <= prob <= 1.0


def test_ml_walkforward_make_model_branches(monkeypatch):
    from src.strategies import ml_strategies as ms

    class DummyModel:
        pass

    monkeypatch.setattr(ms, "XGB_OK", True)
    monkeypatch.setattr(ms, "xgb", types.SimpleNamespace(XGBClassifier=lambda **kwargs: DummyModel()), raising=False)
    strat = ms.MLWalkForwardStrategy(model="xgb")
    assert isinstance(strat._make_model(), DummyModel)

    monkeypatch.setattr(ms, "SK_OK", True)
    monkeypatch.setattr(ms, "RandomForestClassifier", lambda **kwargs: DummyModel(), raising=False)
    strat.model = "rf"
    assert isinstance(strat._make_model(), DummyModel)

    monkeypatch.setattr(ms, "StandardScaler", lambda: object(), raising=False)
    monkeypatch.setattr(ms, "SGDClassifier", lambda **kwargs: DummyModel(), raising=False)
    monkeypatch.setattr(ms, "make_pipeline", lambda *args, **kwargs: DummyModel(), raising=False)
    strat.model = "sgd"
    assert isinstance(strat._make_model(), DummyModel)

    monkeypatch.setattr(ms, "LogisticRegression", lambda **kwargs: DummyModel(), raising=False)
    strat.model = "lr"
    assert isinstance(strat._make_model(), DummyModel)

    monkeypatch.setattr(ms, "TORCH_OK", True)
    monkeypatch.setattr(
        ms,
        "nn",
        types.SimpleNamespace(
            Module=object,
            Linear=lambda *a, **k: None,
            ReLU=lambda *a, **k: None,
            Sequential=lambda *a, **k: None,
        ),
        raising=False,
    )
    strat.model = "mlp"
    model = strat._make_model()
    assert isinstance(model, tuple)
    assert model[0] == "torch_mlp"


def test_ml_walkforward_torch_mlp_branch(monkeypatch):
    df = _dummy_df(rows=60)
    strat = MLWalkForwardStrategy(min_train=10, model="mlp", use_regime_ma=0)
    monkeypatch.setattr(strat, "_make_model", lambda: ("torch_mlp", lambda d: object()))
    monkeypatch.setattr(strat, "_torch_fit", lambda ctor, X, y: object())
    monkeypatch.setattr(strat, "_torch_predict", lambda net, X: 0.7)
    res = strat.generate_signals(df)
    assert res["ML_Prob"].iloc[15] == pytest.approx(0.7)


def test_basic_features_fallback_no_price_columns():
    from src.strategies import ml_strategies as ms

    df = pd.DataFrame({"price": [1, 2, 3]}, index=pd.date_range("2023-01-01", periods=3, freq="D"))
    feats = ms._basic_features(df)
    assert "ret1" in feats.columns


def test_deep_sequence_empty_df_returns_zero():
    strat = DeepSequenceStrategy(arch="lstm", lookback=5)
    res = strat.generate_signals(pd.DataFrame())
    assert res["signal"].eq(0).all()


def test_deep_sequence_no_torch(monkeypatch):
    from src.strategies import ml_strategies as ms

    strat = DeepSequenceStrategy(arch="lstm", lookback=5)
    monkeypatch.setattr(ms, "TORCH_OK", False)
    score = strat._torch_score(np.zeros((3, 2)))
    assert score is None


def test_rl_strategy_empty_df_returns_zero():
    strat = ReinforcementLearningSignalStrategy(lookback=5)
    res = strat.generate_signals(pd.DataFrame())
    assert res["signal"].eq(0).all()


def test_feature_selection_empty_df_returns_zero():
    strat = FeatureSelectionStrategy(top_k=3)
    res = strat.generate_signals(pd.DataFrame())
    assert res["signal"].eq(0).all()


def test_feature_selection_constant_features_fallback():
    idx = pd.date_range("2023-01-01", periods=30, freq="D")
    df = pd.DataFrame(
        {
            "收盘": np.ones(len(idx)) * 100.0,
            "开盘": np.ones(len(idx)) * 100.0,
            "最高": np.ones(len(idx)) * 100.0,
            "最低": np.ones(len(idx)) * 100.0,
            "成交量": np.ones(len(idx)) * 1000.0,
        },
        index=idx,
    )
    strat = FeatureSelectionStrategy(top_k=5)
    res = strat.generate_signals(df)
    assert strat.selected_features
    assert "score" in res


def test_ensemble_voting_empty_strategies_returns_zero():
    strat = EnsembleVotingStrategy([])
    res = strat.generate_signals(_dummy_df(rows=30))
    assert res["signal"].eq(0).all()


def test_ensemble_voting_majority_vote():
    df = _dummy_df(rows=30)

    class DummyStrat:
        def __init__(self, value):
            self.value = value

        def generate_signals(self, frame):
            return pd.DataFrame({"signal": [self.value] * len(frame), "prob": [0.6] * len(frame)})

    ensemble = EnsembleVotingStrategy([DummyStrat(1), DummyStrat(-1)], vote="majority")
    res = ensemble.generate_signals(df)
    assert "prob" in res


def test_regime_adaptive_empty_df_returns_zero():
    strat = RegimeAdaptiveMLStrategy(regime_window=5)
    res = strat.generate_signals(pd.DataFrame())
    assert res["signal"].eq(0).all()
