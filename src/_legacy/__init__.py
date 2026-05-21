"""V6 Phase 8 — Legacy compatibility shim layer.

This package provides the **single mechanism** the project uses to keep old
import paths working after the V6 reshuffle while signalling to plugin
authors and downstream users that those paths should be migrated.

The goal of the cleanup phase is *not* to break callers. It is to:

1. Expose a tiny, testable helper :func:`emit_deprecation` that emits a
   :class:`DeprecationWarning` and a one-line structured log entry the very
   first time a legacy path is touched in a given process.
2. Provide a small :func:`install_module_alias` helper for shim modules to
   register themselves as aliases of their V6 replacement so ``isinstance``,
   ``issubclass`` and ``id()`` based caller code keeps working.
3. Centralise the catalogue of known legacy → canonical replacements in
   :data:`LEGACY_ALIASES` so the deprecation matrix is grep-able and easy
   for PR reviewers to audit.

Usage from a shim module::

    # src/some_old_path.py  (legacy)
    from src._legacy import emit_deprecation
    from src.engines.backtest import *  # noqa: F401,F403

    emit_deprecation(
        legacy="src.some_old_path",
        replacement="src.engines.backtest",
        removed_in="V7.0",
    )

Tests in :mod:`tests.test_legacy_shim` lock in the behaviour.
"""
from __future__ import annotations

import logging
import sys
import threading
import warnings
from types import ModuleType
from typing import Dict, Iterable, Mapping, Tuple

__all__ = [
    "LEGACY_ALIASES",
    "emit_deprecation",
    "install_module_alias",
    "iter_known_aliases",
    "reset_deprecation_cache",
]

# Catalogue of (legacy → canonical) import paths the project has migrated.
# Keep entries sorted alphabetically by legacy name so diffs stay small.
LEGACY_ALIASES: Mapping[str, Tuple[str, str]] = {
    # legacy module path: (canonical V6 path, removed_in)
    # Catalogue is intentionally empty at the start of Phase 8. Entries are
    # added per PR as legacy paths are formally retired, so reviewers can grep
    # this mapping to audit the cleanup matrix in one place.
}

_LOGGER = logging.getLogger("quant_platform.legacy")
_emitted: set[str] = set()
_emitted_lock = threading.Lock()


def emit_deprecation(
    *,
    legacy: str,
    replacement: str,
    removed_in: str = "V7.0",
    stacklevel: int = 3,
) -> None:
    """Emit a one-shot ``DeprecationWarning`` + structured log line.

    The warning is emitted **at most once per process** for each unique
    ``legacy`` identifier so the project's test suite and long-running
    services are not flooded.

    Parameters
    ----------
    legacy:
        Identifier of the legacy entity being imported / called. Conventionally
        the dotted module path, e.g. ``"src.old_path"``.
    replacement:
        Canonical V6 path to migrate to, e.g. ``"src.engines.backtest"``.
    removed_in:
        Free-form version label the entity is scheduled to be removed in.
    stacklevel:
        Forwarded to :func:`warnings.warn` so the warning points at the
        caller, not at this helper.
    """
    with _emitted_lock:
        if legacy in _emitted:
            return
        _emitted.add(legacy)

    message = (
        f"`{legacy}` is a V5 legacy path and will be removed in {removed_in}. "
        f"Import from `{replacement}` instead."
    )
    warnings.warn(message, DeprecationWarning, stacklevel=stacklevel)
    _LOGGER.info(
        "legacy_import",
        extra={
            "event": "legacy_import",
            "legacy": legacy,
            "replacement": replacement,
            "removed_in": removed_in,
        },
    )


def install_module_alias(legacy_name: str, canonical_module: ModuleType) -> None:
    """Register ``legacy_name`` in :data:`sys.modules` as an alias of
    ``canonical_module``.

    This is the recommended way to keep ``import legacy.path`` working when the
    real implementation has moved. Calling code that uses ``id(module)`` or
    ``module.X is module.X`` semantics continues to behave correctly because
    only one module object exists.
    """
    sys.modules[legacy_name] = canonical_module


def iter_known_aliases() -> Iterable[Tuple[str, str, str]]:
    """Yield ``(legacy, canonical, removed_in)`` triples for every known
    legacy alias. Used by tests and docs generators."""
    for legacy, (canonical, removed_in) in LEGACY_ALIASES.items():
        yield legacy, canonical, removed_in


def reset_deprecation_cache() -> None:
    """Clear the one-shot emission cache. Intended for tests only."""
    with _emitted_lock:
        _emitted.clear()


# Internal helper for tests so they can inspect the cache without poking
# at module-private state via ``getattr``.
def _emitted_snapshot() -> Dict[str, None]:  # pragma: no cover - trivial
    with _emitted_lock:
        return {key: None for key in _emitted}
