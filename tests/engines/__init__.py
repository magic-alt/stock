"""Tests for the V6 engines layer (Phase 3).

These tests are purely structural — they verify that the seven engine
subpackages (``data``, ``execution``, ``risk``, ``portfolio``,
``backtest``, ``research``, ``report``) import cleanly, that the names
exported in each subpackage's ``__all__`` resolve, and that each
subpackage's re-exports are the *same* objects as the V5 originals
(identity check, not a copy).
"""

from __future__ import annotations
