"""
Backtrader Plugins Module

Provides pluggable fee/commission and position sizing implementations
for different markets and trading rules.
"""
from __future__ import annotations

from .base import (
    FeePlugin,
    SizerPlugin,
    FEE_REGISTRY,
    SIZER_REGISTRY,
    register_fee,
    register_sizer,
    load_fee,
    load_sizer,
)

# Auto-import all plugins to trigger registration
from . import fees_cn

__all__ = [
    "FeePlugin",
    "SizerPlugin",
    "FEE_REGISTRY",
    "SIZER_REGISTRY",
    "register_fee",
    "register_sizer",
    "load_fee",
    "load_sizer",
]
