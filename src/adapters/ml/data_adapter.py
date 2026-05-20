"""Compatibility alias for the canonical ML data adapter."""

from src.adapters.ml.data import (
    align_to_trading_calendar,
    build_feature_frame,
    normalize_ohlcv_frame,
)

__all__ = ["align_to_trading_calendar", "build_feature_frame", "normalize_ohlcv_frame"]
