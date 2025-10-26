"""
Plugin Base Module

Defines protocols and registry for fee/commission and position sizing plugins.
"""
from __future__ import annotations

from typing import Protocol, Any, Dict, Optional, Type

try:
    import backtrader as bt
except ImportError as exc:
    raise ImportError("backtrader is required: pip install backtrader") from exc


# ---------------------------------------------------------------------------
# Plugin Protocols
# ---------------------------------------------------------------------------

class FeePlugin(Protocol):
    """Protocol for fee/commission calculation plugins."""
    
    def register(self, broker: bt.BrokerBase) -> None:
        """
        Register commission rules with the broker.
        
        Args:
            broker: Backtrader broker instance to configure
        """
        ...


class SizerPlugin(Protocol):
    """Protocol for position sizing plugins."""
    
    def get(self) -> bt.Sizer:
        """
        Return a configured Backtrader Sizer instance.
        
        Returns:
            bt.Sizer: Position sizer implementation
        """
        ...


# ---------------------------------------------------------------------------
# Plugin Registry
# ---------------------------------------------------------------------------

FEE_REGISTRY: Dict[str, Type] = {}
SIZER_REGISTRY: Dict[str, Type] = {}


def register_fee(name: str):
    """
    Decorator to register a fee plugin.
    
    Usage:
        @register_fee("cn_stock")
        class CNStockFee(FeePlugin):
            ...
    
    Args:
        name: Plugin identifier (e.g., "cn_stock", "us_equity", "crypto")
    """
    def decorator(cls):
        FEE_REGISTRY[name] = cls
        return cls
    return decorator


def register_sizer(name: str):
    """
    Decorator to register a position sizer plugin.
    
    Usage:
        @register_sizer("cn_lot100")
        class Lot100Sizer(SizerPlugin):
            ...
    
    Args:
        name: Plugin identifier (e.g., "cn_lot100", "us_whole_shares")
    """
    def decorator(cls):
        SIZER_REGISTRY[name] = cls
        return cls
    return decorator


def load_fee(name: str, **kwargs: Any) -> Optional[FeePlugin]:
    """
    Factory function to create fee plugin instances.
    
    Args:
        name: Plugin name from FEE_REGISTRY
        **kwargs: Plugin-specific initialization parameters
    
    Returns:
        FeePlugin instance or None if not found
    
    Example:
        >>> fee = load_fee("cn_stock", commission_rate=0.0001, stamp_tax_rate=0.0005)
        >>> fee.register(cerebro.broker)
    """
    cls = FEE_REGISTRY.get(name)
    return cls(**kwargs) if cls else None


def load_sizer(name: str, **kwargs: Any) -> Optional[SizerPlugin]:
    """
    Factory function to create sizer plugin instances.
    
    Args:
        name: Plugin name from SIZER_REGISTRY
        **kwargs: Plugin-specific initialization parameters
    
    Returns:
        SizerPlugin instance or None if not found
    
    Example:
        >>> sizer = load_sizer("cn_lot100", lot_size=100)
        >>> cerebro.addsizer(sizer.get())
    """
    cls = SIZER_REGISTRY.get(name)
    return cls(**kwargs) if cls else None
