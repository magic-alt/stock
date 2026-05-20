"""Data engine — V6 ring wrapper over ``src.data_sources``.

Re-exports the V5 data provider, data portal, trading calendar and
quality-check primitives.  These are the canonical implementations that
satisfy the V6 ``DataReader`` / ``DataWriter`` / ``CalendarPort`` ports
defined in :mod:`src.core.contracts.ports.data`.
"""

from __future__ import annotations

from src.data_sources.data_portal import DataPortal, create_portal
from src.data_sources.providers import (
    AkshareProvider,
    DataProvider,
    DataProviderError,
    DataProviderUnavailable,
    QlibProvider,
    TuShareProvider,
    YFinanceProvider,
    get_provider,
)
from src.data_sources.quality import (
    QualitySummary,
    run_quality_checks,
    save_quality_report,
)
from src.data_sources.trading_calendar import (
    TradingCalendar,
    align_frame_to_calendar,
    apply_trading_calendar,
)

__all__ = (
    "DataProvider",
    "DataProviderError",
    "DataProviderUnavailable",
    "AkshareProvider",
    "QlibProvider",
    "YFinanceProvider",
    "TuShareProvider",
    "get_provider",
    "DataPortal",
    "create_portal",
    "TradingCalendar",
    "align_frame_to_calendar",
    "apply_trading_calendar",
    "QualitySummary",
    "run_quality_checks",
    "save_quality_report",
)
