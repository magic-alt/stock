"""V6 engines layer (additive wrappers over V5 modules).

The ``engines`` package is the V6 open-platform's per-domain composition
ring.  Each subpackage groups one logical engine and re-exports the
existing V5 implementations from their canonical locations.  No behavior
is moved or modified; the subpackages exist so V6 plugins, runtimes and
the public SDK can depend on a stable, port-aligned import path:

* :mod:`src.engines.data` — data sourcing and trading calendar
* :mod:`src.engines.execution` — order management, matching, slippage
* :mod:`src.engines.risk` — pre-trade risk and per-account risk manager
* :mod:`src.engines.portfolio` — capital allocation and portfolio mgmt
* :mod:`src.engines.backtest` — historical simulation engine + reports
* :mod:`src.engines.research` — model registry, training, inference
* :mod:`src.engines.report` — report generation and attribution

This is the V6 Phase 3 milestone from ``docs/ROADMAP.md`` §8.5: additive
wrappers only.  V5 modules under ``src/core``, ``src/data_sources``,
``src/simulation``, ``src/backtest``, ``src/mlops`` continue to be the
single source of truth for the implementations re-exported here.
"""

from __future__ import annotations

__all__ = (
    "data",
    "execution",
    "risk",
    "portfolio",
    "backtest",
    "research",
    "report",
)

# Subpackages are imported lazily on first attribute access so that
# importing ``src.engines`` does not eagerly load heavy V5 modules.
