"""Public V6 SDK facade for plugin authors.

The SDK re-exports the frozen contract surface from ``src.core.contracts`` and
the additive plugin registry used by the kernel and CLI tooling.
"""
from __future__ import annotations

from src.core.contracts import *  # noqa: F403
from src.core.contracts import __all__ as _contracts_all
from src.core.plugin_registry import (
    ENTRY_POINT_GROUPS,
    PORT_BY_KIND,
    SPI_METHODS_BY_KIND,
    PluginRecord,
    PluginRegistry,
    PluginTestResult,
    PluginValidationResult,
    instantiate_plugin,
    load_manifest,
    load_object,
)

from .base import BaseFactorPlugin, BaseIndicatorPlugin, BasePlugin, BaseStrategyPlugin, PluginContext

__all__ = [
    *_contracts_all,
    "BaseFactorPlugin",
    "BaseIndicatorPlugin",
    "BasePlugin",
    "BaseStrategyPlugin",
    "ENTRY_POINT_GROUPS",
    "PORT_BY_KIND",
    "PluginContext",
    "PluginRecord",
    "PluginRegistry",
    "PluginTestResult",
    "PluginValidationResult",
    "SPI_METHODS_BY_KIND",
    "instantiate_plugin",
    "load_manifest",
    "load_object",
]
