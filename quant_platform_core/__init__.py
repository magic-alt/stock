"""Compatibility facade for the `quant-platform-core` distribution."""
from __future__ import annotations

from src.core import *  # noqa: F403
from src.core import __all__ as _core_all
from src.core.contracts import CONTRACT_VERSION

__contract_version__ = CONTRACT_VERSION

__all__ = [*_core_all, "__contract_version__"]
