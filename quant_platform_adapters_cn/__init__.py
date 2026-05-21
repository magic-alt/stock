"""Compatibility facade for the ``quant-platform-adapters-cn`` distribution.

This package re-exports the canonical V6 adapter namespaces from
``src.adapters`` so downstream code can import them via the distribution
facade::

    from quant_platform_adapters_cn import data, broker, storage
    from quant_platform_adapters_cn.data import DataPortal

The legacy import path ``from src.adapters.data import DataPortal`` continues
to work and resolves to the same module objects.
"""
from __future__ import annotations

from src.adapters import broker, data, messaging, ml, realtime, storage

ADAPTER_GROUPS = ("data", "realtime", "broker", "storage", "messaging", "ml")

__all__ = [
    "ADAPTER_GROUPS",
    "broker",
    "data",
    "messaging",
    "ml",
    "realtime",
    "storage",
]
