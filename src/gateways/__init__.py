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

from src.gateways.base_live_gateway import (
    BaseLiveGateway,
    GatewayConfig,
    GatewayStatus,
    OrderStatus,
    OrderRequest,
    OrderUpdate,
    TradeUpdate,
    AccountUpdate,
    PositionUpdate,
)

from src.gateways.mappers import (
    SymbolMapper,
    OrderMapper,
    ExchangeCode,
)

# Gateway implementations
from src.gateways.xtquant_gateway import XtQuantGateway
from src.gateways.xtp_gateway import XtpGateway
from src.gateways.hundsun_uft_gateway import HundsunUftGateway


# Gateway factory
GATEWAY_REGISTRY = {
    "xtquant": XtQuantGateway,
    "qmt": XtQuantGateway,
    "miniqmt": XtQuantGateway,
    "xtp": XtpGateway,
    "hundsun": HundsunUftGateway,
    "uft": HundsunUftGateway,
}


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


__all__ = [
    # Base classes
    "BaseLiveGateway",
    "GatewayConfig",
    "GatewayStatus",
    "OrderStatus",
    "OrderRequest",
    "OrderUpdate",
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
