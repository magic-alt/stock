"""
Strategy adapter for AI signal providers.
"""
from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional

import pandas as pd

from src.core.interfaces import BarData, StrategyContext
from src.core.strategy_base import BaseStrategy
from .signals import SignalAction, SignalProvider, SignalSchema, normalize_signal_output

FeatureBuilder = Callable[[StrategyContext, str, BarData, int], pd.DataFrame]


def default_feature_builder(
    ctx: StrategyContext,
    symbol: str,
    bar: BarData,
    lookback: int,
) -> pd.DataFrame:
    """Build a basic OHLCV feature frame from history."""
    hist = ctx.history(symbol, ["open", "high", "low", "close", "volume"], lookback)
    if hist is None or hist.empty:
        frame = pd.DataFrame([bar.to_series()], index=[bar.timestamp])
        frame.index.name = "timestamp"
        return frame
    frame = hist.copy()
    if not isinstance(frame.index, pd.DatetimeIndex):
        frame["timestamp"] = pd.date_range(end=bar.timestamp, periods=len(frame))
        frame = frame.set_index("timestamp")
    frame.index.name = "timestamp"
    return frame


class AISignalStrategy(BaseStrategy):
    """
    Execute AI-generated signals via the unified BaseStrategy interface.
    """
    params = {
        "lookback": 60,
        "allow_short": False,
        "min_confidence": 0.0,
        "default_size": None,
    }

    def __init__(
        self,
        signal_provider: SignalProvider,
        feature_builder: Optional[FeatureBuilder] = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._provider = signal_provider
        self._feature_builder = feature_builder or default_feature_builder

    def on_init(self, ctx: StrategyContext) -> None:
        return None

    def on_bar(self, ctx: StrategyContext, bar: BarData) -> None:
        lookback = int(self.params.get("lookback", 60))
        features = self._feature_builder(ctx, bar.symbol, bar, lookback)
        output = self._provider.predict(features, bar.symbol, bar.timestamp)
        signals = normalize_signal_output(
            output,
            bar.symbol,
            bar.timestamp,
            default_size=self.params.get("default_size"),
        )
        min_conf = float(self.params.get("min_confidence", 0.0))
        for signal in signals:
            if signal.confidence < min_conf:
                continue
            self._execute_signal(ctx, bar, signal)

    def _execute_signal(self, ctx: StrategyContext, bar: BarData, signal: SignalSchema) -> None:
        pos = ctx.positions.get(signal.symbol)
        allow_short = bool(self.params.get("allow_short", False))
        size = signal.size

        if signal.action == SignalAction.BUY:
            if pos is not None and pos.is_long:
                return
            self.buy(ctx, signal.symbol, size=size)
            ctx.log(f"AI signal BUY {signal.symbol}", level="info")
            return

        if signal.action == SignalAction.SELL:
            if pos is None or pos.is_flat:
                if not allow_short:
                    return
            self.sell(ctx, signal.symbol, size=size)
            ctx.log(f"AI signal SELL {signal.symbol}", level="info")
            return

        ctx.log(f"AI signal HOLD {signal.symbol}", level="debug")
