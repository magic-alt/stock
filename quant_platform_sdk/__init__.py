"""Compatibility facade for the `quant-platform-sdk` distribution."""
from __future__ import annotations

from src.sdk import *  # noqa: F403
from src.sdk import __all__ as _sdk_all

__all__ = list(_sdk_all)
