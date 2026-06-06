"""Adapter namespace convergence tests."""

from __future__ import annotations

from src.adapters.broker import GatewayConfig as CanonicalGatewayConfig
from src.adapters.broker import create_gateway as canonical_create_gateway
from src.adapters.broker.base_live_gateway import (
    BaseLiveGateway as CanonicalBaseLiveGateway,
)
from src.adapters.data import DataPortal as CanonicalDataPortal
from src.adapters.data.providers import DataProvider as CanonicalDataProvider
from src.adapters.data.providers import get_provider as canonical_get_provider
from src.adapters.messaging import MessageBus as CanonicalMessageBus
from src.adapters.ml.data import (
    normalize_ohlcv_frame as canonical_normalize_ohlcv_frame,
)
from src.adapters.realtime import RealtimeDataManager as CanonicalRealtimeDataManager
from src.adapters.realtime.providers import (
    SinaDataProvider as CanonicalSinaDataProvider,
)
from src.adapters.storage import MemoryRepository as CanonicalMemoryRepository
from src.adapters.storage import SQLiteDataManager as CanonicalSQLiteDataManager
from src.adapters.storage.repository import (
    create_repository as canonical_create_repository,
)
from src.core.message_bus import MessageBus
from src.core.realtime_data import RealtimeDataManager, SinaDataProvider
from src.core.repository import MemoryRepository, create_repository
from src.data_sources.data_portal import DataPortal
from src.data_sources.db_manager import SQLiteDataManager
from src.data_sources.providers import DataProvider, get_provider
from src.gateways import GatewayConfig, create_gateway
from src.gateways.base_live_gateway import BaseLiveGateway
from src.mlops.data_adapter import normalize_ohlcv_frame

def test_data_adapter_namespace_reexports_legacy_data_objects() -> None:
    assert CanonicalDataProvider is DataProvider
    assert canonical_get_provider is get_provider
    assert CanonicalDataPortal is DataPortal

def test_realtime_adapter_namespace_reexports_legacy_realtime_objects() -> None:
    assert CanonicalRealtimeDataManager is RealtimeDataManager
    assert CanonicalSinaDataProvider is SinaDataProvider

def test_broker_adapter_namespace_reexports_legacy_gateway_objects() -> None:
    assert CanonicalGatewayConfig is GatewayConfig
    assert CanonicalBaseLiveGateway is BaseLiveGateway
    assert canonical_create_gateway is create_gateway
    assert canonical_create_gateway(
        "xtquant", GatewayConfig(account_id="demo", broker="xtquant"), None
    ).__class__.__name__ == ("XtQuantGateway")

def test_storage_adapter_namespace_reexports_legacy_storage_objects() -> None:
    assert CanonicalSQLiteDataManager is SQLiteDataManager
    assert CanonicalMemoryRepository is MemoryRepository
    assert canonical_create_repository is create_repository

def test_ml_adapter_namespace_reexports_legacy_ml_objects() -> None:
    assert canonical_normalize_ohlcv_frame is normalize_ohlcv_frame

def test_messaging_adapter_namespace_reexports_legacy_message_bus_objects() -> None:
    assert CanonicalMessageBus is MessageBus
