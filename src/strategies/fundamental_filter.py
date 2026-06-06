"""
Fundamental Filter Strategy
============================

Uses jetbot financial-fact exports as fundamental-factor filters for
stock selection and strategy gating.

This module provides two integration modes:

1. **Standalone filter** – ``FundamentalFilter`` scores symbols based on
   configurable thresholds for the five core metrics and returns
   pass/fail decisions for each symbol.

2. **Backtrader strategy wrapper** – ``FundamentalFilterStrategy`` applies
   the fundamental filter as a pre-screen before any technical signal is
   acted upon. Only symbols that pass the fundamental gate will be
   considered for entry.

Core metrics consumed from jetbot exports:

- ``revenue_growth``      – prefer positive growth
- ``net_profit_growth``   – prefer positive growth
- ``gross_margin``        – prefer higher margins
- ``operating_cash_flow`` – prefer positive cash flow
- ``debt_ratio``          – prefer lower leverage
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pandas as pd

from src.data_sources.jetbot_facts import (
    CORE_METRICS,
    JetbotFactsProvider,
    get_jetbot_facts_provider,
)

logger = logging.getLogger(__name__)


# ── Threshold configuration ───────────────────────────────────────────────

@dataclass
class FundamentalThresholds:
    """Configurable thresholds for fundamental-factor scoring.

    Each metric has a ``min`` (lower bound) and ``max`` (upper bound).
    Set to ``None`` to disable that bound.

    A fact passes the gate when ``min <= value <= max`` for every
    enabled metric. Metrics not present in the jetbot export are
    skipped (not treated as failure) unless ``require_all=True``.
    """

    revenue_growth_min: Optional[float] = 0.0
    revenue_growth_max: Optional[float] = None
    net_profit_growth_min: Optional[float] = 0.0
    net_profit_growth_max: Optional[float] = None
    gross_margin_min: Optional[float] = 0.10
    gross_margin_max: Optional[float] = None
    operating_cash_flow_min: Optional[float] = 0.0
    operating_cash_flow_max: Optional[float] = None
    debt_ratio_min: Optional[float] = None
    debt_ratio_max: Optional[float] = 0.70
    require_all: bool = False
    min_score: float = 0.0

    def get_bounds(self, metric: str) -> Tuple[Optional[float], Optional[float]]:
        """Return (min, max) bounds for a given metric."""
        mapping = {
            "revenue_growth": (self.revenue_growth_min, self.revenue_growth_max),
            "net_profit_growth": (self.net_profit_growth_min, self.net_profit_growth_max),
            "gross_margin": (self.gross_margin_min, self.gross_margin_max),
            "operating_cash_flow": (self.operating_cash_flow_min, self.operating_cash_flow_max),
            "debt_ratio": (self.debt_ratio_min, self.debt_ratio_max),
        }
        return mapping.get(metric, (None, None))


# ── Scoring engine ────────────────────────────────────────────────────────

@dataclass
class FilterResult:
    """Result of applying the fundamental filter to one symbol."""

    symbol: str
    passed: bool
    score: float
    details: Dict[str, Dict] = field(default_factory=dict)

    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return f"{self.symbol}: {status} (score={self.score:.2f})"


class FundamentalFilter:
    """Score and gate symbols based on jetbot financial-fact exports.

    Parameters
    ----------
    provider : JetbotFactsProvider
        Loaded provider with export data.
    thresholds : FundamentalThresholds
        Configurable metric bounds.
    weights : dict, optional
        Per-metric weights for composite scoring. Defaults to equal weight.
    """

    def __init__(
        self,
        provider: JetbotFactsProvider,
        thresholds: FundamentalThresholds | None = None,
        weights: Dict[str, float] | None = None,
    ):
        self.provider = provider
        self.thresholds = thresholds or FundamentalThresholds()
        self.weights = weights or {m: 1.0 for m in CORE_METRICS}

    def score_symbol(self, symbol: str, period: str | None = None) -> FilterResult:
        """Score a single symbol against the configured thresholds."""
        metrics = self.provider.get_metrics_dict(symbol, period=period)
        return self._evaluate(symbol, metrics)

    def score_all(self, period: str | None = None) -> List[FilterResult]:
        """Score all loaded symbols and return sorted results."""
        results: List[FilterResult] = []
        for symbol in self.provider.list_symbols():
            result = self.score_symbol(symbol, period=period)
            results.append(result)
        results.sort(key=lambda r: r.score, reverse=True)
        return results

    def filter_passed(self, period: str | None = None) -> List[str]:
        """Return symbols that pass the fundamental gate."""
        return [r.symbol for r in self.score_all(period=period) if r.passed]

    def filter_dataframe(self, df: pd.DataFrame, symbol_col: str = "symbol") -> pd.DataFrame:
        """Filter an OHLCV DataFrame to only include fundamentally sound symbols.

        Parameters
        ----------
        df : pd.DataFrame
            Input DataFrame with at least a ``symbol_col`` column.
        symbol_col : str
            Name of the column containing stock symbols.

        Returns
        -------
        pd.DataFrame
            Filtered DataFrame with only symbols that pass the gate.
        """
        passed = set(self.filter_passed())
        if not passed:
            logger.warning("No symbols passed the fundamental filter")
            return df.iloc[0:0]
        return df[df[symbol_col].isin(passed)]

    # ── Internal ──────────────────────────────────────────────────────

    def _evaluate(self, symbol: str, metrics: Dict[str, float]) -> FilterResult:
        details: Dict[str, Dict] = {}
        total_score = 0.0
        total_weight = 0.0
        all_pass = True
        checked_count = 0

        for metric in CORE_METRICS:
            value = metrics.get(metric)
            lo, hi = self.thresholds.get_bounds(metric)
            weight = self.weights.get(metric, 1.0)

            if value is None:
                if self.thresholds.require_all:
                    all_pass = False
                    details[metric] = {"status": "missing", "required": True}
                else:
                    details[metric] = {"status": "missing", "required": False}
                continue

            checked_count += 1
            in_range = True

            if lo is not None and value < lo:
                in_range = False
            if hi is not None and value > hi:
                in_range = False

            if not in_range:
                all_pass = False

            # Normalise score contribution: 1.0 = perfectly in range
            if in_range:
                metric_score = 1.0
            else:
                # Distance-based penalty
                if lo is not None and value < lo:
                    denom = abs(lo) if lo != 0 else 1.0
                    metric_score = max(0.0, 1.0 - abs(value - lo) / denom)
                elif hi is not None and value > hi:
                    denom = abs(hi) if hi != 0 else 1.0
                    metric_score = max(0.0, 1.0 - abs(value - hi) / denom)
                else:
                    metric_score = 0.0

            total_score += metric_score * weight
            total_weight += weight
            details[metric] = {
                "value": value,
                "bounds": (lo, hi),
                "pass": in_range,
                "score": round(metric_score, 4),
            }

        composite = total_score / total_weight if total_weight > 0 else 0.0
        passed = all_pass and composite >= self.thresholds.min_score

        return FilterResult(
            symbol=symbol,
            passed=passed,
            score=round(composite, 4),
            details=details,
        )


# ── Backtrader strategy wrapper ──────────────────────────────────────────

try:
    import backtrader as bt

    class FundamentalFilterStrategy(bt.Strategy):
        """Backtrader strategy that applies jetbot fundamental filters.

        This strategy acts as a **pre-screen gate**: it only allows entry
        for symbols that pass the fundamental filter. Technical signals
        from a child strategy are still needed for actual entry/exit.

        Parameters
        ----------
        export_dir : str
            Path to jetbot export directory.
        min_confidence : float
            Minimum fact confidence threshold.
        revenue_growth_min : float
            Minimum revenue growth rate.
        gross_margin_min : float
            Minimum gross margin.
        debt_ratio_max : float
            Maximum debt ratio.
        """

        params = (
            ("export_dir", "./jetbot_exports"),
            ("min_confidence", 0.5),
            ("revenue_growth_min", 0.0),
            ("net_profit_growth_min", 0.0),
            ("gross_margin_min", 0.10),
            ("operating_cash_flow_min", 0.0),
            ("debt_ratio_max", 0.70),
            ("require_all", False),
        )

        def __init__(self):
            self._provider = get_jetbot_facts_provider(
                export_dir=self.p.export_dir,
                min_confidence=self.p.min_confidence,
            )
            self._thresholds = FundamentalThresholds(
                revenue_growth_min=self.p.revenue_growth_min,
                net_profit_growth_min=self.p.net_profit_growth_min,
                gross_margin_min=self.p.gross_margin_min,
                operating_cash_flow_min=self.p.operating_cash_flow_min,
                debt_ratio_max=self.p.debt_ratio_max,
                require_all=self.p.require_all,
            )
            self._filter = FundamentalFilter(self._provider, self._thresholds)
            self._passed_symbols: set = set()
            self._loaded = False

        def start(self):
            """Load fundamental data and pre-compute passed symbols."""
            self._provider.load()
            self._passed_symbols = set(self._filter.filter_passed())
            self._loaded = True
            logger.info(
                "FundamentalFilterStrategy: %d / %d symbols passed",
                len(self._passed_symbols),
                len(self._provider.list_symbols()),
            )

        def next(self):
            """Gate: do nothing if the current symbol fails the fundamental filter."""
            if not self._loaded:
                return

            symbol = self._get_symbol()
            if symbol not in self._passed_symbols:
                return  # Skip this symbol entirely

            # Placeholder: in a real setup, delegate to a child strategy
            # for technical entry/exit signals.

        def _get_symbol(self) -> str:
            """Extract the stock symbol from the current data feed."""
            name = self.data._name if hasattr(self.data, "_name") else ""
            return name

        def get_filter_result(self, symbol: str) -> Optional[FilterResult]:
            """Return the detailed filter result for a symbol."""
            return self._filter.score_symbol(symbol)

        def get_passed_symbols(self) -> List[str]:
            """Return all symbols that passed the fundamental gate."""
            return sorted(self._passed_symbols)

except ImportError:
    # backtrader not installed — strategy wrapper unavailable
    pass


# ── Convenience functions ─────────────────────────────────────────────────

def create_fundamental_filter(
    export_dir: str = "./jetbot_exports",
    min_confidence: float = 0.5,
    **threshold_kwargs,
) -> FundamentalFilter:
    """Create a FundamentalFilter with sensible defaults.

    Any keyword arguments are passed to ``FundamentalThresholds``.
    """
    provider = get_jetbot_facts_provider(
        export_dir=export_dir,
        min_confidence=min_confidence,
    )
    thresholds = FundamentalThresholds(**threshold_kwargs)
    return FundamentalFilter(provider, thresholds)


def score_symbols_from_exports(
    export_dir: str = "./jetbot_exports",
    period: str | None = None,
) -> List[FilterResult]:
    """One-shot scoring of all symbols in the export directory."""
    filt = create_fundamental_filter(export_dir=export_dir)
    return filt.score_all(period=period)
