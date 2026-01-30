"""
AI signal schema and normalization helpers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Protocol, Sequence

import pandas as pd


class SignalAction(str, Enum):
    """Standardized signal action."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass(slots=True)
class SignalSchema:
    """Normalized signal payload for AI/ML strategies."""
    symbol: str
    timestamp: datetime
    action: SignalAction
    size: Optional[float] = None
    score: float = 0.0
    confidence: float = 0.0
    model_id: Optional[str] = None
    horizon: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_buy(self) -> bool:
        return self.action == SignalAction.BUY

    @property
    def is_sell(self) -> bool:
        return self.action == SignalAction.SELL

    @property
    def is_hold(self) -> bool:
        return self.action == SignalAction.HOLD


class SignalProvider(Protocol):
    """Protocol for AI signal providers."""
    def predict(self, features: pd.DataFrame, symbol: str, timestamp: datetime) -> Any:
        """Return signal output for the given features."""
        ...


def _action_from_value(value: Any) -> SignalAction:
    if isinstance(value, SignalAction):
        return value
    if isinstance(value, str):
        val = value.strip().lower()
        if val in ("buy", "long", "1", "up"):
            return SignalAction.BUY
        if val in ("sell", "short", "-1", "down"):
            return SignalAction.SELL
        return SignalAction.HOLD
    try:
        num = float(value)
    except (TypeError, ValueError):
        return SignalAction.HOLD
    if num > 0:
        return SignalAction.BUY
    if num < 0:
        return SignalAction.SELL
    return SignalAction.HOLD


def _signal_from_frame(
    frame: pd.DataFrame,
    symbol: str,
    timestamp: datetime,
    default_size: Optional[float],
) -> SignalSchema:
    if frame.empty:
        return SignalSchema(symbol=symbol, timestamp=timestamp, action=SignalAction.HOLD)
    row = frame.iloc[-1]
    action_val = row.get("action") if "action" in frame.columns else row.get("signal", 0)
    action = _action_from_value(action_val)
    score = float(row.get("score", 0.0)) if "score" in row else 0.0
    confidence = float(row.get("confidence", row.get("prob", 0.0))) if ("confidence" in row or "prob" in row) else 0.0
    size = row.get("size", default_size) if isinstance(row, pd.Series) else default_size
    model_id = row.get("model_id") if "model_id" in row else None
    return SignalSchema(
        symbol=symbol,
        timestamp=timestamp,
        action=action,
        size=None if pd.isna(size) else size,
        score=score,
        confidence=confidence,
        model_id=model_id,
    )


def normalize_signal_output(
    output: Any,
    symbol: str,
    timestamp: datetime,
    default_size: Optional[float] = None,
) -> List[SignalSchema]:
    """
    Normalize AI framework outputs into SignalSchema list.

    Supported outputs:
    - SignalSchema
    - Iterable[SignalSchema]
    - pandas.DataFrame (expects last row with signal/action)
    - pandas.Series (signal/action as value or key)
    - scalar numeric / string (1, -1, "buy", "sell")
    """
    if output is None:
        return []
    if isinstance(output, SignalSchema):
        return [output]
    if isinstance(output, pd.DataFrame):
        return [_signal_from_frame(output, symbol, timestamp, default_size)]
    if isinstance(output, pd.Series):
        action_val = output.get("action", output.get("signal", output.iloc[-1] if len(output) else 0))
        signal = SignalSchema(
            symbol=symbol,
            timestamp=timestamp,
            action=_action_from_value(action_val),
            size=output.get("size", default_size),
            score=float(output.get("score", 0.0)),
            confidence=float(output.get("confidence", output.get("prob", 0.0))),
            model_id=output.get("model_id"),
        )
        return [signal]
    if isinstance(output, Sequence) and not isinstance(output, (str, bytes)):
        if output and all(isinstance(item, SignalSchema) for item in output):
            return list(output)
    return [SignalSchema(symbol=symbol, timestamp=timestamp, action=_action_from_value(output), size=default_size)]
