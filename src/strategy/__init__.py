"""
Strategy Templates Module

Provides simplified strategy development interface decoupled from execution engines.
"""
from __future__ import annotations

from .template import StrategyTemplate, BacktraderAdapter

__all__ = ["StrategyTemplate", "BacktraderAdapter"]
