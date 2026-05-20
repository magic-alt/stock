"""Base classes for V6 plugin authors.

These classes are intentionally small. The hard compatibility contract lives
in ``src.core.contracts`` Protocols and DTOs; the base classes provide a
convenient, import-stable starting point for common plugin kinds.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from src.core.contracts import PluginManifest


@dataclass(frozen=True, slots=True)
class PluginContext:
    """Runtime context passed to plugins when a host chooses to call ``on_load``."""

    kernel: Optional[Any] = None
    config: Mapping[str, Any] | None = None


class BasePlugin:
    """Common lifecycle hooks shared by SDK plugin base classes."""

    manifest: Optional[PluginManifest] = None

    def on_load(self, context: Optional[PluginContext] = None) -> None:
        """Called by hosts after a plugin is accepted by the registry."""

    def on_unload(self) -> None:
        """Called by hosts before a plugin is removed from the registry."""


class BaseStrategyPlugin(BasePlugin):
    """Base class for strategy plugins.

    Strategies receive a mapping of symbol to tabular OHLCV-like data and
    return a mapping of symbol to signal strength in ``[-1.0, 1.0]``.
    """

    def generate_signals(self, data: Mapping[str, Any]) -> Mapping[str, float]:
        raise NotImplementedError


class BaseIndicatorPlugin(BasePlugin):
    """Base class for technical indicator plugins."""

    def compute(self, data: Any, **params: Any) -> Any:
        raise NotImplementedError


class BaseFactorPlugin(BasePlugin):
    """Base class for research factor plugins."""

    def compute(self, data: Any, **params: Any) -> Any:
        raise NotImplementedError


__all__ = [
    "BaseFactorPlugin",
    "BaseIndicatorPlugin",
    "BasePlugin",
    "BaseStrategyPlugin",
    "PluginContext",
]
