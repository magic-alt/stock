"""
Live Trading Gateways Module

Provides implementations for A-share live trading connections:
- XtQuantGateway: QMT/MiniQMT via xtquant SDK
- XtpGateway: 中泰XTP极速柜台
- HundsunUftGateway: 恒生UFT/极速接口

V3.2.0: Initial release - Live trading gateway implementations

Usage:
    >>> from src.gateways import XtQuantGateway, GatewayConfig
    >>> 
    >>> config = GatewayConfig(
    ...     account_id="YOUR_ACCOUNT",
    ...     broker="xtquant",
    ... )
    >>> gateway = XtQuantGateway(config, event_engine)
    >>> gateway.connect()
    >>> 
    >>> # Send order
    >>> order_id = gateway.send_order("600519.SH", "buy", 100, price=1800.0)
"""
from __future__ import annotations

from importlib import import_module
from typing import Dict, Iterator, Tuple

from src.gateways.base_live_gateway import (
    BaseLiveGateway,
    GatewayConfig,
    GatewayStatus,
    GatewayUnavailable,
    OrderStatus,
    OrderRequest,
    OrderUpdate,
    OrderStateMachine,
    OrderStateTransition,
    InvalidOrderStateTransition,
    TradeUpdate,
    AccountUpdate,
    PositionUpdate,
)

from src.gateways.mappers import (
    SymbolMapper,
    OrderMapper,
    ExchangeCode,
)

_GATEWAY_IMPORTS: Dict[str, Tuple[str, str]] = {
    "xtquant": ("src.gateways.xtquant_gateway", "XtQuantGateway"),
    "qmt": ("src.gateways.xtquant_gateway", "XtQuantGateway"),
    "miniqmt": ("src.gateways.xtquant_gateway", "XtQuantGateway"),
    "xtp": ("src.gateways.xtp_gateway", "XtpGateway"),
    "hundsun": ("src.gateways.hundsun_uft_gateway", "HundsunUftGateway"),
    "uft": ("src.gateways.hundsun_uft_gateway", "HundsunUftGateway"),
}


def _load_gateway_class(module_name: str, class_name: str):
    module = import_module(module_name)
    return getattr(module, class_name)


class _LazyGatewayRegistry(dict):
    """Mapping that resolves concrete gateway classes only when requested."""

    def __getitem__(self, key: str):
        module_name, class_name = super().__getitem__(key)
        return _load_gateway_class(module_name, class_name)

    def get(self, key: str, default=None):
        if key not in self:
            return default
        return self[key]

    def items(self) -> Iterator[Tuple[str, type]]:  # type: ignore[override]
        for key in self.keys():
            yield key, self[key]

    def values(self) -> Iterator[type]:  # type: ignore[override]
        for key in self.keys():
            yield self[key]


# Gateway factory. Values are lazily resolved to avoid probing commercial SDKs
# when callers only need base classes/configuration objects.
GATEWAY_REGISTRY = _LazyGatewayRegistry(_GATEWAY_IMPORTS)


def create_gateway(broker: str, config: GatewayConfig, event_queue, logger=None):
    """
    Factory function to create appropriate gateway.
    
    Args:
        broker: Broker type (xtquant, xtp, hundsun, etc.)
        config: Gateway configuration
        event_queue: Queue for event publishing
        logger: Optional logger instance
        
    Returns:
        Gateway instance
        
    Raises:
        ValueError: If broker type is not supported
    """
    broker_lower = broker.lower()
    if broker_lower not in GATEWAY_REGISTRY:
        available = ", ".join(GATEWAY_REGISTRY.keys())
        raise ValueError(f"Unknown broker: {broker}. Available: {available}")
    
    gateway_cls = GATEWAY_REGISTRY[broker_lower]
    return gateway_cls(config, event_queue, logger)


def __getattr__(name: str):
    if name in {"XtQuantGateway", "XtpGateway", "HundsunUftGateway"}:
        for module_name, class_name in _GATEWAY_IMPORTS.values():
            if class_name == name:
                value = _load_gateway_class(module_name, class_name)
                globals()[name] = value
                return value
    raise AttributeError(f"module 'src.gateways' has no attribute {name!r}")


__all__ = [
    # Base classes
    "BaseLiveGateway",
    "GatewayConfig",
    "GatewayStatus",
    "GatewayUnavailable",
    "OrderStatus",
    "OrderRequest",
    "OrderUpdate",
    "OrderStateMachine",
    "OrderStateTransition",
    "InvalidOrderStateTransition",
    "TradeUpdate",
    "AccountUpdate",
    "PositionUpdate",
    
    # Mappers
    "SymbolMapper",
    "OrderMapper",
    "ExchangeCode",
    
    # Gateway implementations
    "XtQuantGateway",
    "XtpGateway",
    "HundsunUftGateway",
    
    # Factory
    "create_gateway",
    "GATEWAY_REGISTRY",
]
