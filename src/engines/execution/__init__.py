"""Execution engine — V6 ring wrapper over OMS and matching layer.

Re-exports order management (``src.core.order_manager``), the simulated
matching engine and supporting execution models / slippage models from
:mod:`src.simulation`.  These satisfy the V6 ``ExecutionPort`` /
``OrderRouterPort`` ports defined in
:mod:`src.core.contracts.ports.execution`.
"""

from __future__ import annotations

from src.core.order_manager import ManagedOrder, OrderEvent, OrderManager
from src.simulation.execution_models import (
    AlwaysFill,
    ExecutionDelayModel,
    FillProbabilityModel,
    FixedDelay,
    VolumeBasedFill,
)
from src.simulation.matching_engine import AShareRules, MatchingEngine
from src.simulation.order import (
    Order,
    OrderDirection,
    OrderStatus,
    OrderType,
    Trade,
)
from src.simulation.order_book import OrderBook
from src.simulation.slippage import (
    FixedSlippage,
    NoSlippage,
    PercentSlippage,
    SlippageModel,
    SquareRootImpactSlippage,
    VolumeShareSlippage,
)

__all__ = (
    "OrderManager",
    "ManagedOrder",
    "OrderEvent",
    "MatchingEngine",
    "AShareRules",
    "Order",
    "OrderStatus",
    "OrderType",
    "OrderDirection",
    "Trade",
    "OrderBook",
    "SlippageModel",
    "FixedSlippage",
    "PercentSlippage",
    "VolumeShareSlippage",
    "SquareRootImpactSlippage",
    "NoSlippage",
    "FillProbabilityModel",
    "AlwaysFill",
    "VolumeBasedFill",
    "ExecutionDelayModel",
    "FixedDelay",
)
