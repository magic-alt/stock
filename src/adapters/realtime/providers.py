"""Canonical realtime provider adapter exports."""

from __future__ import annotations

from src.adapters.realtime.feed import (
    AKShareDataProvider,
    EastmoneyDataProvider,
    HTTPPollingDataProvider,
    SimulationDataProvider,
    SinaDataProvider,
    TencentDataProvider,
    WebSocketDataProvider,
    create_realtime_provider,
)

__all__ = [
    "AKShareDataProvider",
    "EastmoneyDataProvider",
    "HTTPPollingDataProvider",
    "SimulationDataProvider",
    "SinaDataProvider",
    "TencentDataProvider",
    "WebSocketDataProvider",
    "create_realtime_provider",
]
