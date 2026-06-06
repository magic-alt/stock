"""
Lightweight optimization utilities for strategy combinations.

This package is intentionally dependency-light so it can be covered in tests
without pulling in the heavy backtest engine or external data sources.
"""

from __future__ import annotations

from .combo_optimizer import optimize_portfolio, load_nav_series, PortfolioResult  # noqa: F401
