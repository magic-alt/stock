"""Broker gateway adapter exports."""

from importlib import import_module
from typing import Dict, Iterator, Tuple

from src.adapters.broker.base_live_gateway import (
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
from src.adapters.broker.mappers import ExchangeCode, OrderMapper, SymbolMapper

_GATEWAY_IMPORTS: Dict[str, Tuple[str, str]] = {
    "xtquant": ("src.adapters.broker.xtquant_gateway", "XtQuantGateway"),
    "qmt": ("src.adapters.broker.xtquant_gateway", "XtQuantGateway"),
    "miniqmt": ("src.adapters.broker.xtquant_gateway", "XtQuantGateway"),
    "xtp": ("src.adapters.broker.xtp_gateway", "XtpGateway"),
    "hundsun": ("src.adapters.broker.hundsun_uft_gateway", "HundsunUftGateway"),
    "uft": ("src.adapters.broker.hundsun_uft_gateway", "HundsunUftGateway"),
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


GATEWAY_REGISTRY = _LazyGatewayRegistry(_GATEWAY_IMPORTS)


def create_gateway(broker: str, config: GatewayConfig, event_queue, logger=None):
    """Create a concrete broker gateway by broker name."""
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
    raise AttributeError(f"module 'src.adapters.broker' has no attribute {name!r}")


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
