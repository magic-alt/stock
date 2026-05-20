"""V6 Open Platform port Protocols.

A *port* is a structural Protocol describing what the kernel/engines expect
from a plugin or adapter. All ports are :py:func:`typing.runtime_checkable`
so test code can ``isinstance(adapter, FooPort)`` without inheritance.

The ports are grouped by concern; this ``__init__`` re-exports every port
so callers can write ``from src.core.contracts.ports import DataProviderPort``.
"""
from __future__ import annotations

from .data import (
    DataProviderPort,
    PortfolioReaderPort,
    RealtimeFeedPort,
    StoragePort,
)
from .execution import (
    BrokerGatewayPort,
    FillModelPort,
    OrderRouterPort,
    SlippageModelPort,
)
from .messaging import MessageBusPort
from .observability import AuditPort, MetricsPort, TracerPort
from .risk import AdmissionGatePort, RiskRulePort
from .services import MLAdapterPort, ReportPort, SchedulerPort, VaultPort

ALL_PORTS = (
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

__all__ = [
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
