"""
Execution models: fill probability and delay modeling.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

import pandas as pd

from .order import Order


class FillProbabilityModel(Protocol):
    """Protocol for probabilistic fill decision."""

    def fill_probability(self, order: Order, bar: Optional[pd.Series] = None) -> float:
        """Return fill probability between 0 and 1."""
        ...

    def should_fill(self, order: Order, bar: Optional[pd.Series] = None) -> bool:
        """Return True if the order should fill."""
        ...


@dataclass
class AlwaysFill:
    """Always fill orders."""

    def fill_probability(self, order: Order, bar: Optional[pd.Series] = None) -> float:
        return 1.0

    def should_fill(self, order: Order, bar: Optional[pd.Series] = None) -> bool:
        return True


@dataclass
class VolumeBasedFill:
    """
    Probability proportional to volume participation.

    If bar volume is missing, returns 0 probability.
    """

    participation_rate: float = 0.1

    def fill_probability(self, order: Order, bar: Optional[pd.Series] = None) -> float:
        if bar is None or "volume" not in bar:
            return 0.0
        volume = float(bar.get("volume", 0.0))
        if volume <= 0:
            return 0.0
        # Expected fill ratio based on participation
        expected = volume * self.participation_rate
        prob = expected / max(order.quantity, 1e-9)
        return float(min(max(prob, 0.0), 1.0))

    def should_fill(self, order: Order, bar: Optional[pd.Series] = None) -> bool:
        return self.fill_probability(order, bar) >= 1.0


class ExecutionDelayModel(Protocol):
    """Protocol for execution delay modeling."""

    def delay_bars(self, order: Order) -> int:
        """Return the delay in bars before the order is active."""
        ...


@dataclass
class FixedDelay:
    """Fixed delay in bars."""

    bars: int = 0

    def delay_bars(self, order: Order) -> int:
        return max(int(self.bars), 0)
