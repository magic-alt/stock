"""Concrete engine backends for the backtest framework.

Importing this package registers built-in backends with
:class:`src.backtest.engine_base.EngineRegistry`.
"""
from __future__ import annotations

from src.backtest.engine_base import EngineRegistry  # re-export for convenience

__all__ = ["EngineRegistry"]
