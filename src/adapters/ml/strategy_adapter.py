"""Compatibility alias for the canonical AI signal strategy adapter."""

from src.adapters.ml.strategy import AISignalStrategy, default_feature_builder

__all__ = ["AISignalStrategy", "default_feature_builder"]
