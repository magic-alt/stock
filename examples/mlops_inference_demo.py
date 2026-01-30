"""
Minimal example: connect a predictor to AISignalStrategy via InferenceService.
"""
from __future__ import annotations

import pandas as pd

from src.core.interfaces import BarData
from src.mlops.inference import InferenceService
from src.mlops.strategy_adapter import AISignalStrategy


class DummyPredictor:
    def predict(self, features: pd.DataFrame):
        # Always return buy signal
        return 1


def demo() -> None:
    service = InferenceService(predictor=DummyPredictor(), model_id="demo-model")
    strategy = AISignalStrategy(service, lookback=30)
    bar = BarData(symbol="DEMO", timestamp=pd.Timestamp("2024-01-01"), open=10, high=11, low=9, close=10.5, volume=100)
    print("Strategy ready:", strategy, "Latest bar:", bar)


if __name__ == "__main__":
    demo()
