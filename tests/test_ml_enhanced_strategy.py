import numpy as np
import pandas as pd
import types

import pytest

import src.strategies.ml_enhanced_strategy as mes


def _dummy_df(rows: int = 80) -> pd.DataFrame:
    idx = pd.date_range("2023-01-01", periods=rows, freq="D")
    base = np.linspace(50, 60, rows) + np.random.normal(0, 0.4, rows)
    return pd.DataFrame(
        {
            "open": base + np.random.normal(0, 0.2, rows),
            "high": base + np.random.uniform(0.3, 1.0, rows),
            "low": base - np.random.uniform(0.3, 1.0, rows),
            "close": base + np.random.normal(0, 0.3, rows),
            "volume": np.random.randint(100_000, 500_000, rows),
        },
        index=idx,
    )


def test_ml_enhanced_feature_engineering_columns():
    df = _dummy_df()
    feats = mes.MLEnhancedStrategy._ta(df)
    expected = {
        "ret1",
        "vol_ratio_5_20",
        "dist_ma5",
        "rsi14",
        "macd_pct",
        "bb_position",
        "vol_ratio_5",
        "body_pct",
    }
    assert expected.issubset(set(feats.columns))
    assert feats.isna().sum().sum() == 0


def test_ml_enhanced_generate_signals_dummy_model(monkeypatch):
    df = _dummy_df(rows=60)

    class DummyScaler:
        def fit_transform(self, X):
            return X

        def transform(self, X):
            return X

    class DummyModel:
        def fit(self, X, y):
            return self

        def predict_proba(self, X):
            return np.tile([0.3, 0.7], (len(X), 1))

    strat = mes.MLEnhancedStrategy(min_train=10, prob_threshold=0.6)
    strat._scaler = DummyScaler()
    strat._get_model = lambda: DummyModel()
    monkeypatch.setattr(mes, "_HAS_SKLEARN", True)

    res = strat.generate_signals(df)
    assert {"Signal", "Probability"} <= set(res.columns)
    assert res["Probability"].iloc[15] == 0.7
    assert res["Signal"].iloc[15] == 1


def test_ml_enhanced_generate_signals_no_sklearn(monkeypatch):
    df = _dummy_df(rows=40)
    strat = mes.MLEnhancedStrategy(min_train=10)
    monkeypatch.setattr(mes, "_HAS_SKLEARN", False)
    res = strat.generate_signals(df)
    assert res["Signal"].eq(0).all()
    assert res["Probability"].eq(0.5).all()


def test_ml_ensemble_strategy_averages_probabilities():
    df = _dummy_df(rows=40)

    class DummyStrategy:
        def __init__(self, prob: float):
            self.prob = prob

        def generate_signals(self, frame: pd.DataFrame) -> pd.DataFrame:
            out = frame.copy()
            out["Probability"] = self.prob
            out["Signal"] = 0
            return out

    ensemble = mes.MLEnsembleStrategy(prob_threshold=0.65, min_train=10)
    ensemble._models = {
        "a": DummyStrategy(0.7),
        "b": DummyStrategy(0.9),
    }

    res = ensemble.generate_signals(df)
    assert res["Probability"].iloc[-1] == 0.8
    assert res["Signal"].iloc[-1] == 1


def test_ml_ensemble_strategy_empty_models_returns_zero_signal():
    df = _dummy_df(rows=40)
    ensemble = mes.MLEnsembleStrategy(prob_threshold=0.6, min_train=10)
    ensemble._models = {}
    res = ensemble.generate_signals(df)
    assert res["Signal"].eq(0).all()
    assert res["Probability"].eq(0.5).all()


def test_ml_enhanced_get_model_branches(monkeypatch):
    strat = mes.MLEnhancedStrategy(min_train=10)

    class DummyModel:
        pass

    monkeypatch.setattr(mes, "_HAS_XGB", True)
    monkeypatch.setattr(mes, "xgb", types.SimpleNamespace(XGBClassifier=lambda **kwargs: DummyModel()), raising=False)
    strat.model_type = "xgb"
    assert isinstance(strat._get_model(), DummyModel)

    monkeypatch.setattr(mes, "_HAS_SKLEARN", True)
    monkeypatch.setattr(mes, "GradientBoostingClassifier", lambda **kwargs: DummyModel())
    strat.model_type = "gb"
    assert isinstance(strat._get_model(), DummyModel)

    monkeypatch.setattr(mes, "RandomForestClassifier", lambda **kwargs: DummyModel())
    strat.model_type = "rf"
    assert isinstance(strat._get_model(), DummyModel)


def test_ml_enhanced_generate_signals_chinese_columns(monkeypatch):
    idx = pd.date_range("2023-01-01", periods=60, freq="D")
    df = pd.DataFrame(
        {
            "开盘": np.linspace(10, 12, len(idx)),
            "最高": np.linspace(10.5, 12.5, len(idx)),
            "最低": np.linspace(9.5, 11.5, len(idx)),
            "收盘": np.linspace(10, 12, len(idx)),
            "成交量": np.random.randint(10_000, 50_000, len(idx)),
        },
        index=idx,
    )

    class DummyScaler:
        def fit_transform(self, X):
            return X

        def transform(self, X):
            return X

    class DummyModel:
        def fit(self, X, y):
            return self

        def predict_proba(self, X):
            return np.tile([0.6, 0.4], (len(X), 1))

    strat = mes.MLEnhancedStrategy(min_train=10, prob_threshold=0.55)
    strat._scaler = DummyScaler()
    strat._get_model = lambda: DummyModel()
    monkeypatch.setattr(mes, "_HAS_SKLEARN", True)

    res = strat.generate_signals(df)
    assert res["Signal"].iloc[15] == -1


def test_ml_enhanced_get_feature_importance():
    strat = mes.MLEnhancedStrategy(min_train=10)

    class DummyModel:
        feature_importances_ = [0.2, 0.8]

    strat._model = DummyModel()
    importance = strat.get_feature_importance()
    assert importance == {0: 0.2, 1: 0.8}


def test_ml_enhanced_coerce_casts_types():
    out = mes._coerce_ml_enhanced(
        {"label_horizon": "2", "min_train": "50", "prob_threshold": "0.65", "retrain_interval": "10"}
    )
    assert out["label_horizon"] == 2
    assert out["min_train"] == 50
    assert out["prob_threshold"] == 0.65
    assert out["retrain_interval"] == 10


def test_ml_enhanced_training_failure_warning(monkeypatch):
    df = _dummy_df(rows=60)

    class DummyScaler:
        def fit_transform(self, X):
            return X

        def transform(self, X):
            return X

    class DummyModel:
        def fit(self, X, y):
            raise RuntimeError("boom")

    strat = mes.MLEnhancedStrategy(min_train=10, prob_threshold=0.6)
    strat._scaler = DummyScaler()
    strat._get_model = lambda: DummyModel()
    monkeypatch.setattr(mes, "_HAS_SKLEARN", True)

    res = strat.generate_signals(df)
    assert "Signal" in res
