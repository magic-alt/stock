"""Broker gateway adapter exports.

Delegates to the canonical :mod:`src.gateways` package for the shared
factory infrastructure (_LazyGatewayRegistry, create_gateway, etc.)
and only maintains the adapter-level re-export surface.
"""
from __future__ import annotations

from src.gateways import (
    GATEWAY_REGISTRY,
    _GATEWAY_IMPORTS,
    _LazyGatewayRegistry,
    _load_gateway_class,
    create_gateway,
)
from src.gateways.base_live_gateway import (
    AccountUpdate,
    BaseLiveGateway,
    GatewayConfig,
    GatewayStatus,
    GatewayUnavailable,
    InvalidOrderStateTransition,
    OrderRequest,
    OrderStateMachine,
    OrderStateTransition,
    OrderStatus,
    OrderUpdate,
    PositionUpdate,
    TradeUpdate,
)
from src.gateways.mappers import ExchangeCode, OrderMapper, SymbolMapper


__all__ = [
    "AccountUpdate",
    "BaseLiveGateway",
    "ExchangeCode",
    "GATEWAY_REGISTRY",
    "GatewayConfig",
    "GatewayStatus",
    "GatewayUnavailable",
    "HundsunUftGateway",
    "InvalidOrderStateTransition",
    "OrderMapper",
    "OrderRequest",
    "OrderStateMachine",
    "OrderStateTransition",
    "OrderStatus",
    "OrderUpdate",
    "PositionUpdate",
    "SymbolMapper",
    "TradeUpdate",
    "XtQuantGateway",
    "XtpGateway",
    "create_gateway",
]
