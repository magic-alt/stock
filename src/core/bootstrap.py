"""
Kernel Bootstrap Module

Provides ``bootstrap_kernel()`` and ``get_bootstrapped_kernel()`` helper
functions that construct a :class:`~src.core.kernel.PlatformKernel` instance
and register all core components that are available in the current runtime
environment.

Every optional component is wrapped in a ``try/except`` block so that
missing dependencies (e.g. ``backtrader`` or a database driver) do not
prevent the kernel from starting.

Usage::

    from src.core.bootstrap import bootstrap_kernel, get_bootstrapped_kernel

    kernel = bootstrap_kernel()
    print(kernel.names())  # ['event_engine', ...]

    # later
    kernel.start_all()
"""
from __future__ import annotations

import logging
from typing import Optional

from src.core.kernel import PlatformKernel

logger = logging.getLogger(__name__)


def bootstrap_kernel(kernel: Optional[PlatformKernel] = None) -> PlatformKernel:
    """Create (or augment) a ``PlatformKernel`` with all discoverable components.

    Components attempted (in order):

    1. ``EventEngine`` from :mod:`src.core.events`
    2. ``BacktestEngine`` from :mod:`src.backtest.engine` (optional, requires ``backtrader``)
    3. ``RiskManagerV2`` from :mod:`src.core.risk_manager_v2` (optional)
    4. ``OrderManager`` from :mod:`src.core.order_manager` (optional)
    5. ``DataPortal`` from :mod:`src.data_sources.data_portal` (optional)

    Args:
        kernel: An existing kernel to register into. If ``None``, a fresh
                :class:`PlatformKernel` is created.

    Returns:
        The kernel instance with all available components registered.
    """
    kernel = kernel or PlatformKernel()

    # 1. EventEngine
    try:
        from src.core.events import EventEngine

        engine = EventEngine()
        kernel.register(
            name="event_engine",
            component=engine,
            start=engine.start,
            stop=engine.stop,
            tags=("core", "events"),
        )
    except Exception as exc:
        logger.warning("bootstrap: EventEngine registration skipped — %s", exc)

    # 2. BacktestEngine (requires backtrader)
    try:
        from src.backtest.engine import BacktestEngine

        bt_engine = BacktestEngine()
        kernel.register(
            name="backtest_engine",
            component=bt_engine,
            tags=("core", "backtest"),
        )
    except Exception as exc:
        logger.warning("bootstrap: BacktestEngine registration skipped — %s", exc)

    # 3. RiskManagerV2
    try:
        from src.core.risk_manager_v2 import RiskManagerV2

        risk_mgr = RiskManagerV2()
        kernel.register(
            name="risk_manager",
            component=risk_mgr,
            tags=("core", "risk"),
        )
    except Exception as exc:
        logger.warning("bootstrap: RiskManagerV2 registration skipped — %s", exc)

    # 4. OrderManager
    try:
        from src.core.order_manager import OrderManager

        order_mgr = OrderManager()
        kernel.register(
            name="order_manager",
            component=order_mgr,
            tags=("core", "oms"),
        )
    except Exception as exc:
        logger.warning("bootstrap: OrderManager registration skipped — %s", exc)

    # 5. DataPortal
    try:
        from src.data_sources.data_portal import DataPortal

        portal = DataPortal(provider="akshare")
        kernel.register(
            name="data_portal",
            component=portal,
            tags=("core", "data"),
        )
    except Exception as exc:
        logger.warning("bootstrap: DataPortal registration skipped — %s", exc)

    return kernel


_bootstrapped_kernel: Optional[PlatformKernel] = None


def get_bootstrapped_kernel() -> PlatformKernel:
    """Return a lazily-bootstrapped process-wide :class:`PlatformKernel`.

    The first call constructs and caches the kernel; subsequent calls
    return the same instance. Tests should call :func:`reset_bootstrapped_kernel`
    to clear the cache between runs.
    """
    global _bootstrapped_kernel
    if _bootstrapped_kernel is None:
        _bootstrapped_kernel = bootstrap_kernel()
    return _bootstrapped_kernel


def reset_bootstrapped_kernel() -> None:
    """Discard the cached bootstrapped kernel (for tests)."""
    global _bootstrapped_kernel
    _bootstrapped_kernel = None


__all__ = [
    "bootstrap_kernel",
    "get_bootstrapped_kernel",
    "reset_bootstrapped_kernel",
]
