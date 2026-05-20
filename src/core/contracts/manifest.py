"""Plugin manifest for the V6 open-platform :class:`PluginRegistry`.

Every third-party plugin distribution ships a manifest object alongside its
entry-point declaration. The kernel uses the manifest to:

* gate-load plugins whose ``contract_version`` is incompatible with the
  running SDK (see :mod:`src.core.contracts.version`);
* refuse plugins requesting permissions that the operator has not granted;
* emit lifecycle events with stable identifying metadata (``id``, ``kind``,
  ``version``) on the message bus.

The manifest is intentionally light: it does **not** describe the plugin's
runtime API — that role belongs to the relevant
:mod:`src.core.contracts.ports` Protocol.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import FrozenSet, Mapping, Optional, Tuple

from .version import CONTRACT_VERSION, is_compatible


# Stable identifiers for plugin kinds. These mirror the entry-point groups
# declared in ``pyproject.toml`` so the registry can resolve a plugin's
# expected port from its declared kind without string parsing.
PLUGIN_KINDS: FrozenSet[str] = frozenset({
    "strategy",
    "indicator",
    "factor",
    "data_provider",
    "realtime_feed",
    "gateway",
    "storage",
    "risk_rule",
    "fill_model",
    "report",
    "scheduler",
    "ml_adapter",
    "messaging",
    "admission_gate",
})


# Stable capability tokens advertised by plugins. The registry does NOT
# enforce these — they are informational hints surfaced in the UI and
# audit log. Permissions (below) are what get enforced.
KNOWN_CAPABILITIES: FrozenSet[str] = frozenset({
    "intraday",
    "daily",
    "level2",
    "cn_a_share",
    "futures",
    "options",
    "vector_backtest",
    "event_driven",
    "realtime",
    "historical",
})


# Stable permission tokens. The registry refuses plugins requesting tokens
# the operator has not allow-listed. Operators allow-list via configuration.
KNOWN_PERMISSIONS: FrozenSet[str] = frozenset({
    "filesystem.read",
    "filesystem.write",
    "network.outbound",
    "vault.read",
    "vault.write",
    "subprocess.spawn",
    "kernel.bus.publish",
    "kernel.bus.subscribe",
})


@dataclass(frozen=True, slots=True)
class PluginManifest:
    """Metadata a plugin advertises to the :class:`PluginRegistry`."""

    id: str
    name: str
    version: str
    kind: str
    entry_point: str
    contract_version: str = CONTRACT_VERSION
    description: str = ""
    author: str = ""
    homepage: Optional[str] = None
    capabilities: Tuple[str, ...] = field(default_factory=tuple)
    permissions: Tuple[str, ...] = field(default_factory=tuple)
    requires: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("PluginManifest.id must be non-empty")
        if not self.id.replace("_", "").replace("-", "").replace(".", "").isalnum():
            raise ValueError(
                f"PluginManifest.id {self.id!r} must contain only alphanumerics, '_', '-' or '.'"
            )
        if not self.name:
            raise ValueError("PluginManifest.name must be non-empty")
        if not self.version:
            raise ValueError("PluginManifest.version must be non-empty")
        if self.kind not in PLUGIN_KINDS:
            raise ValueError(
                f"PluginManifest.kind {self.kind!r} not in known kinds: {sorted(PLUGIN_KINDS)}"
            )
        if ":" not in self.entry_point:
            raise ValueError(
                f"PluginManifest.entry_point {self.entry_point!r} must be of the form 'module.path:attribute'"
            )
        object.__setattr__(self, "capabilities", tuple(self.capabilities))
        object.__setattr__(self, "permissions", tuple(self.permissions))

    def is_contract_compatible(self, available: str = CONTRACT_VERSION) -> bool:
        """Return ``True`` if this plugin can load against ``available``."""
        return is_compatible(self.contract_version, available)

    def unknown_capabilities(self) -> Tuple[str, ...]:
        return tuple(c for c in self.capabilities if c not in KNOWN_CAPABILITIES)

    def unknown_permissions(self) -> Tuple[str, ...]:
        return tuple(p for p in self.permissions if p not in KNOWN_PERMISSIONS)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "kind": self.kind,
            "entry_point": self.entry_point,
            "contract_version": self.contract_version,
            "description": self.description,
            "author": self.author,
            "homepage": self.homepage,
            "capabilities": list(self.capabilities),
            "permissions": list(self.permissions),
            "requires": dict(self.requires),
        }


__all__ = [
    "KNOWN_CAPABILITIES",
    "KNOWN_PERMISSIONS",
    "PLUGIN_KINDS",
    "PluginManifest",
]
