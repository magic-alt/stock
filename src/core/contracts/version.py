"""V6 Open Platform contract version.

Plugin authors and adapters pin against this version to declare which SDK
surface they target. The kernel's :class:`PluginRegistry` (Phase 5) will
verify that a plugin's declared ``contract_version`` is compatible with the
running kernel at load time.

Versioning rules
----------------

* Major bumps are reserved for **breaking** changes to DTO field semantics
  or port method signatures. Plugins pinned to an older major MUST be
  refused by the registry.
* Minor bumps are reserved for **additive** changes: new optional DTO
  fields with safe defaults, new ports, new manifest keys. Older plugins
  remain loadable.
* Patch bumps are reserved for documentation- or annotation-only
  clarifications that change neither runtime behaviour nor surface.

Phase 2 freezes the V6 SDK surface at ``0.1.0``. The version stays in
the ``0.x`` range until Phase 7 (distribution split) when the SDK ships
as ``quant_platform_sdk`` and is bumped to ``1.0.0``.
"""
from __future__ import annotations

CONTRACT_VERSION: str = "0.1.0"
"""Semantic version of the V6 open-platform contract surface."""


def is_compatible(required: str, available: str = CONTRACT_VERSION) -> bool:
    """Return ``True`` if a plugin requiring ``required`` can load against ``available``.

    Compatibility rule (matches the versioning policy above):

    * Same major.
    * ``available`` minor >= ``required`` minor.

    Pre-1.0 (``0.x``) the major is always ``0`` and we treat the minor as
    the breaking-change axis, so we require *exact minor match*. Once the
    contract reaches ``1.0.0`` the standard semver rule applies.
    """
    try:
        rmaj, rmin, _ = _parse(required)
        amaj, amin, _ = _parse(available)
    except ValueError:
        return False
    if amaj != rmaj:
        return False
    if amaj == 0:
        return amin == rmin
    return amin >= rmin


def _parse(version: str) -> tuple[int, int, int]:
    parts = version.split(".")
    if len(parts) != 3:
        raise ValueError(f"Invalid contract version: {version!r}")
    return int(parts[0]), int(parts[1]), int(parts[2])


__all__ = ["CONTRACT_VERSION", "is_compatible"]
