"""V6 Open Platform contract surface (Single Source of Truth).

Plugin authors and adapter implementors depend on **this package only** —
no other ``src.core`` symbol is part of the V6 SDK promise. Anything not
re-exported here is internal and may change without a contract version bump.

The package is organised in three layers:

* :mod:`.version` — :data:`CONTRACT_VERSION` constant + compatibility helper.
* :mod:`.dto` — immutable, validated value objects exchanged across
  port boundaries (Bar, Tick, Order, Fill, Signal, …).
* :mod:`.ports` — :class:`typing.Protocol` definitions describing what
  the kernel/engines require from a plugin (DataProviderPort,
  BrokerGatewayPort, RiskRulePort, …).
* :mod:`.manifest` — :class:`PluginManifest` describing the plugin
  itself (id, version, declared contract version, requested permissions).

Phase 2 freezes this surface at ``CONTRACT_VERSION = '0.1.0'``. V5 modules
(``src/core/interfaces.py``, ``src/core/objects.py``, ``src/core/plugin.py``)
are intentionally NOT touched; both type systems coexist until Phase 3
introduces conversion shims at the engine boundary.
"""
from __future__ import annotations

from .dto import (
    AccountSnapshot,
    AssetClass,
    Bar,
    BacktestResult,
    BookLevel,
    Fill,
    Instrument,
    Order,
    OrderBookSnapshot,
    OrderStatus,
    OrderType,
    Position,
    RiskCheckResult,
    RiskDecision,
    Side,
    Signal,
    Tick,
    TimeInForce,
)
from .manifest import KNOWN_CAPABILITIES, KNOWN_PERMISSIONS, PLUGIN_KINDS, PluginManifest
from .ports import (
    ALL_PORTS,
    AdmissionGatePort,
    AuditPort,
    BrokerGatewayPort,
    DataProviderPort,
    FillModelPort,
    MLAdapterPort,
    MessageBusPort,
    MetricsPort,
    OrderRouterPort,
    PortfolioReaderPort,
    RealtimeFeedPort,
    ReportPort,
    RiskRulePort,
    SchedulerPort,
    SlippageModelPort,
    StoragePort,
    TracerPort,
    VaultPort,
)
from .version import CONTRACT_VERSION, is_compatible

__all__ = [
    # version
    "CONTRACT_VERSION",
    "is_compatible",
    # enums
    "AssetClass",
    "OrderStatus",
    "OrderType",
    "RiskDecision",
    "Side",
    "TimeInForce",
    # DTOs
    "AccountSnapshot",
    "Bar",
    "BacktestResult",
    "BookLevel",
    "Fill",
    "Instrument",
    "Order",
    "OrderBookSnapshot",
    "Position",
    "RiskCheckResult",
    "Signal",
    "Tick",
    # manifest
    "KNOWN_CAPABILITIES",
    "KNOWN_PERMISSIONS",
    "PLUGIN_KINDS",
    "PluginManifest",
    # ports
    "ALL_PORTS",
    "AdmissionGatePort",
    "AuditPort",
    "BrokerGatewayPort",
    "DataProviderPort",
    "FillModelPort",
    "MLAdapterPort",
    "MessageBusPort",
    "MetricsPort",
    "OrderRouterPort",
    "PortfolioReaderPort",
    "RealtimeFeedPort",
    "ReportPort",
    "RiskRulePort",
    "SchedulerPort",
    "SlippageModelPort",
    "StoragePort",
    "TracerPort",
    "VaultPort",
]
