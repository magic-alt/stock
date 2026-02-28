"""
Plugin System (V5.0-E-1) — Discover, load, and manage plugins.

Provides:
- PluginBase: abstract base class for all plugins
- PluginManager: discover, load, unload, query plugins
- Plugin types: strategy, datasource, gateway, indicator, report, factor

Usage:
    >>> from src.core.plugin import PluginManager
    >>> pm = PluginManager()
    >>> pm.discover(["./plugins"])
    >>> pm.list_plugins()
    [PluginInfo(name='my_plugin', version='1.0', plugin_type='strategy')]
"""
from __future__ import annotations

import importlib
import importlib.util
import inspect
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Type


# ---------------------------------------------------------------------------
# Plugin types
# ---------------------------------------------------------------------------

PLUGIN_TYPES = {"strategy", "datasource", "gateway", "indicator", "report", "factor"}


# ---------------------------------------------------------------------------
# PluginBase
# ---------------------------------------------------------------------------

class PluginBase:
    """Abstract base for all plugins."""

    name: str = ""
    version: str = "0.1.0"
    plugin_type: str = "strategy"
    description: str = ""
    author: str = ""

    def on_load(self) -> None:
        """Called when plugin is loaded."""
        pass

    def on_unload(self) -> None:
        """Called when plugin is unloaded."""
        pass


# ---------------------------------------------------------------------------
# PluginInfo
# ---------------------------------------------------------------------------

@dataclass
class PluginInfo:
    """Metadata about a loaded plugin."""
    name: str
    version: str
    plugin_type: str
    description: str = ""
    author: str = ""
    module_path: str = ""
    enabled: bool = True


# ---------------------------------------------------------------------------
# PluginManager
# ---------------------------------------------------------------------------

class PluginManager:
    """Plugin discovery, loading, and lifecycle management."""

    def __init__(self):
        self._plugins: Dict[str, PluginBase] = {}
        self._info: Dict[str, PluginInfo] = {}
        self._hooks: Dict[str, List[Callable]] = {}

    # -- Discovery -----------------------------------------------------------

    def discover(self, paths: List[str]) -> List[PluginInfo]:
        """Scan directories for plugin modules.

        A plugin module must contain at least one class subclassing PluginBase.

        Args:
            paths: List of directory paths to scan.

        Returns:
            List of discovered plugin infos.
        """
        discovered: List[PluginInfo] = []
        for dir_path in paths:
            p = Path(dir_path)
            if not p.is_dir():
                continue
            for py_file in p.glob("*.py"):
                if py_file.name.startswith("_"):
                    continue
                plugin_classes = self._scan_module(py_file)
                for cls in plugin_classes:
                    info = PluginInfo(
                        name=getattr(cls, "name", py_file.stem),
                        version=getattr(cls, "version", "0.1.0"),
                        plugin_type=getattr(cls, "plugin_type", "strategy"),
                        description=getattr(cls, "description", ""),
                        author=getattr(cls, "author", ""),
                        module_path=str(py_file),
                    )
                    discovered.append(info)
        return discovered

    def _scan_module(self, path: Path) -> List[Type[PluginBase]]:
        """Import a module and return all PluginBase subclasses."""
        try:
            spec = importlib.util.spec_from_file_location(path.stem, str(path))
            if spec is None or spec.loader is None:
                return []
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            classes = []
            for _, obj in inspect.getmembers(mod, inspect.isclass):
                if issubclass(obj, PluginBase) and obj is not PluginBase:
                    classes.append(obj)
            return classes
        except Exception:
            return []

    # -- Loading / unloading -------------------------------------------------

    def load(self, plugin_id: str, plugin_class: Optional[Type[PluginBase]] = None, **kwargs) -> bool:
        """Load and activate a plugin.

        Args:
            plugin_id: Unique identifier for this plugin instance.
            plugin_class: The plugin class to instantiate (optional if already discovered).

        Returns:
            True if loaded successfully.
        """
        if plugin_id in self._plugins:
            return False  # already loaded

        if plugin_class is None:
            return False

        try:
            instance = plugin_class(**kwargs) if kwargs else plugin_class()
            instance.on_load()
            self._plugins[plugin_id] = instance
            self._info[plugin_id] = PluginInfo(
                name=getattr(instance, "name", plugin_id),
                version=getattr(instance, "version", "0.1.0"),
                plugin_type=getattr(instance, "plugin_type", "strategy"),
                description=getattr(instance, "description", ""),
                author=getattr(instance, "author", ""),
                enabled=True,
            )
            return True
        except Exception:
            return False

    def unload(self, plugin_id: str) -> bool:
        """Unload a plugin.

        Returns:
            True if unloaded successfully.
        """
        plugin = self._plugins.pop(plugin_id, None)
        if plugin is None:
            return False
        try:
            plugin.on_unload()
        except Exception:
            pass
        self._info.pop(plugin_id, None)
        return True

    # -- Query ---------------------------------------------------------------

    def get(self, plugin_id: str) -> Optional[PluginBase]:
        """Get a loaded plugin instance."""
        return self._plugins.get(plugin_id)

    def list_plugins(self) -> List[PluginInfo]:
        """List all loaded plugins."""
        return list(self._info.values())

    def list_by_type(self, plugin_type: str) -> List[PluginInfo]:
        """List plugins of a specific type."""
        return [info for info in self._info.values() if info.plugin_type == plugin_type]

    def is_loaded(self, plugin_id: str) -> bool:
        """Check if a plugin is currently loaded."""
        return plugin_id in self._plugins

    # -- Hooks ---------------------------------------------------------------

    def register_hook(self, event: str, handler: Callable) -> None:
        """Register a hook for a lifecycle event."""
        self._hooks.setdefault(event, []).append(handler)

    def fire_hook(self, event: str, **kwargs) -> List[Any]:
        """Fire all handlers for an event."""
        results = []
        for handler in self._hooks.get(event, []):
            try:
                results.append(handler(**kwargs))
            except Exception:
                results.append(None)
        return results

    def clear(self) -> None:
        """Unload all plugins and clear hooks."""
        for pid in list(self._plugins.keys()):
            self.unload(pid)
        self._hooks.clear()


__all__ = ["PluginBase", "PluginInfo", "PluginManager", "PLUGIN_TYPES"]
