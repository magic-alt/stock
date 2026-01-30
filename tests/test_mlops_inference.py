from __future__ import annotations

from datetime import datetime

import pandas as pd

from src.core.interfaces import AccountInfo, BarData, PositionInfo
from src.mlops.inference import BatchInferenceRunner, InferenceService


class DummyPredictor:
    def __init__(self, output):
        self.output = output

    def predict(self, features: pd.DataFrame):
        return self.output


class DummyContext:
    def __init__(self) -> None:
        self._account = AccountInfo()
        self._positions: dict[str, PositionInfo] = {}

    @property
    def account(self) -> AccountInfo:
        return self._account

    @property
    def positions(self) -> dict[str, PositionInfo]:
        return self._positions

    def current_price(self, symbol: str, field: str = "close") -> float | None:
        return 1.0

    def get_bar(self, symbol: str) -> BarData | None:
        return None

    def history(self, symbol: str, fields: list[str], periods: int, frequency: str = "1d") -> pd.DataFrame:
        return pd.DataFrame({f: [1.0] * periods for f in fields})

    def buy(self, symbol: str, size: float | None = None, price: float | None = None, order_type: str = "market") -> str:
        return "buy"

    def sell(self, symbol: str, size: float | None = None, price: float | None = None, order_type: str = "market") -> str:
        return "sell"

    def cancel(self, order_id: str) -> bool:
        return True

    def log(self, message: str, level: str = "info") -> None:
        return None

    def get_datetime(self) -> datetime:
        return datetime.utcnow()


def test_inference_service_sets_model_id() -> None:
    service = InferenceService(predictor=DummyPredictor(1), model_id="model-1")
    signals = service.predict(pd.DataFrame({"close": [1, 2]}), "TEST", datetime(2024, 1, 1))
    assert signals[0].model_id == "model-1"


def test_batch_inference_runner_runs() -> None:
    service = InferenceService(predictor=DummyPredictor(1), model_id="model-1")
    runner = BatchInferenceRunner(service, lookback=2)
    ctx = DummyContext()
    bars = [
        BarData(symbol="A", timestamp=datetime(2024, 1, 1), open=1, high=1, low=1, close=1, volume=1),
        BarData(symbol="B", timestamp=datetime(2024, 1, 2), open=1, high=1, low=1, close=1, volume=1),
    ]
    out = runner.run(ctx, bars)
    assert len(out) == 2
