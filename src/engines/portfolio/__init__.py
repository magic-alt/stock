"""Portfolio engine — V6 ring wrapper over capital allocation primitives.

Re-exports the V5 portfolio manager, capital allocator and account
manager.  Together these satisfy the V6 ``PortfolioPort`` /
``AccountPort`` ports.
"""

from __future__ import annotations

from src.core.account_manager import AccountInfo, AccountManager
from src.core.capital_allocator import (
    AccountCapital,
    CapitalAllocationResult,
    CapitalAllocator,
)
from src.core.portfolio import AllocationResult, PortfolioManager

__all__ = (
    "PortfolioManager",
    "AllocationResult",
    "CapitalAllocator",
    "CapitalAllocationResult",
    "AccountCapital",
    "AccountManager",
    "AccountInfo",
)
