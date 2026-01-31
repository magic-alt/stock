"""
Simulation Module

Provides order matching engine and slippage models for paper trading simulation.
"""
from .order import Order, Trade, OrderStatus, OrderType, OrderDirection
from .order_book import OrderBook
from .slippage import (
    SlippageModel,
    FixedSlippage,
    PercentSlippage,
    VolumeShareSlippage,
    SquareRootImpactSlippage,
)
from .execution_models import AlwaysFill, VolumeBasedFill, FixedDelay
from .matching_engine import MatchingEngine

__all__ = [
    # Order types
    "Order",
    "Trade",
    "OrderStatus",
    "OrderType",
    "OrderDirection",
    # Order book
    "OrderBook",
    # Slippage models
    "SlippageModel",
    "FixedSlippage",
    "PercentSlippage",
    "VolumeShareSlippage",
    "SquareRootImpactSlippage",
    # Execution models
    "AlwaysFill",
    "VolumeBasedFill",
    "FixedDelay",
    # Matching engine
    "MatchingEngine",
]
