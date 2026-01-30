"""
Local inference utilities for AI signal integration.
"""
from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Dict, Iterable, List, Optional, Protocol

import pandas as pd

from src.core.interfaces import BarData, StrategyContext
from .signals import SignalSchema, normalize_signal_output
from .strategy_adapter import FeatureBuilder, default_feature_builder


class Predictor(Protocol):
    """Protocol for model predictor."""
    def predict(self, features: pd.DataFrame) -> Any:
        ...


@dataclass
class InferenceService:
    """Wrap a predictor and normalize outputs into SignalSchema."""
    predictor: Predictor
    model_id: Optional[str] = None

    def predict(self, features: pd.DataFrame, symbol: str, timestamp) -> List[SignalSchema]:
        output = self.predictor.predict(features)
        signals = normalize_signal_output(output, symbol, timestamp)
        if self.model_id:
            for signal in signals:
                if not signal.model_id:
                    signal.model_id = self.model_id
        return signals


class BatchInferenceRunner:
    """Batch inference runner for multiple bars."""

    def __init__(
        self,
        service: InferenceService,
        *,
        feature_builder: Optional[FeatureBuilder] = None,
        lookback: int = 60,
    ) -> None:
        self.service = service
        self.feature_builder = feature_builder or default_feature_builder
        self.lookback = lookback

    def run(self, ctx: StrategyContext, bars: Iterable[BarData]) -> List[SignalSchema]:
        signals: List[SignalSchema] = []
        for bar in bars:
            features = self.feature_builder(ctx, bar.symbol, bar, self.lookback)
            signals.extend(self.service.predict(features, bar.symbol, bar.timestamp))
        return signals


def benchmark_inference(
    service: InferenceService,
    features: pd.DataFrame,
    *,
    symbol: str,
    timestamp,
    iterations: int = 50,
) -> Dict[str, float]:
    """Simple latency benchmark for local inference."""
    if iterations <= 0:
        return {"avg_ms": 0.0, "p95_ms": 0.0}
    timings: List[float] = []
    for _ in range(iterations):
        start = perf_counter()
        service.predict(features, symbol, timestamp)
        timings.append((perf_counter() - start) * 1000)
    timings.sort()
    avg_ms = sum(timings) / len(timings)
    p95_ms = timings[int(len(timings) * 0.95) - 1]
    return {"avg_ms": avg_ms, "p95_ms": p95_ms}
