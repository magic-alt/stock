"""
Jetbot Financial Facts Provider
================================

Reads normalised financial-fact envelopes exported by the ``jetbot`` project
and exposes them as fundamental-factor data for strategy filtering and
backtest integration.

The provider consumes JSON files that follow the ``jetbot`` export schema v1.0::

    {
        "symbol": "600519.SH",
        "company": "贵州茅台",
        "period": "2025Q4",
        "facts": [
            {"metric": "revenue_growth", "value": 0.125, "unit": "ratio", ...}
        ]
    }

Supported core metrics
----------------------
- ``revenue_growth``      – year-over-year revenue change ratio
- ``net_profit_growth``   – year-over-year net profit change ratio
- ``gross_margin``        – gross profit / revenue
- ``operating_cash_flow`` – net cash from operating activities
- ``debt_ratio``          – total liabilities / total assets
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import pandas as pd

logger = logging.getLogger(__name__)

# ── Export schema constants ────────────────────────────────────────────────

SUPPORTED_SCHEMA_VERSIONS = {"1.0"}
CORE_METRICS = (
    "revenue_growth",
    "net_profit_growth",
    "gross_margin",
    "operating_cash_flow",
    "debt_ratio",
)


# ── Data models ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class JetbotFactRecord:
    """A single financial metric from a jetbot export envelope."""

    symbol: str
    company: str
    period: str
    period_end: Optional[str]
    metric: str
    value: float
    unit: str
    label: str
    confidence: float
    source_page: Optional[int] = None
    source_document: Optional[str] = None
    raw_value: Optional[float] = None
    raw_unit: Optional[str] = None
    computation: Optional[str] = None


@dataclass
class JetbotExportEnvelope:
    """Parsed jetbot export envelope."""

    doc_id: str
    symbol: Optional[str]
    company: Optional[str]
    period: Optional[str]
    period_end: Optional[str]
    source_document: Optional[str]
    facts: List[JetbotFactRecord] = field(default_factory=list)
    risk_signals: List[Dict] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    schema_version: str = "1.0"
    generated_at: Optional[str] = None


# ── Provider class ─────────────────────────────────────────────────────────

class JetbotFactsProvider:
    """Load and query jetbot financial-fact exports.

    Parameters
    ----------
    export_dir : str or Path
        Directory containing jetbot export JSON files.
    min_confidence : float
        Minimum confidence threshold for accepting a fact (0.0–1.0).

    Examples
    --------
    >>> provider = JetbotFactsProvider("./jetbot_exports")
    >>> df = provider.load_facts_dataframe()
    >>> df[df["metric"] == "gross_margin"][["symbol", "company", "value"]]
    """

    name: str = "jetbot_facts"

    def __init__(
        self,
        export_dir: str | Path = "./jetbot_exports",
        min_confidence: float = 0.5,
    ):
        self.export_dir = Path(export_dir)
        self.min_confidence = min_confidence
        self._envelopes: List[JetbotExportEnvelope] = []
        self._loaded = False

    # ── Loading ────────────────────────────────────────────────────────

    def load(self, rescan: bool = False) -> List[JetbotExportEnvelope]:
        """Scan ``export_dir`` for ``*.json`` files and parse them.

        Returns the list of successfully parsed envelopes.
        """
        if self._loaded and not rescan:
            return self._envelopes

        self._envelopes = []
        if not self.export_dir.exists():
            logger.warning("Jetbot export directory not found: %s", self.export_dir)
            return self._envelopes

        for path in sorted(self.export_dir.glob("*.json")):
            try:
                envelope = self._parse_file(path)
                self._envelopes.append(envelope)
            except Exception as exc:
                logger.warning("Failed to parse %s: %s", path.name, exc)

        self._loaded = True
        logger.info(
            "Loaded %d jetbot export envelopes from %s",
            len(self._envelopes),
            self.export_dir,
        )
        return self._envelopes

    def load_from_json(self, data: str | dict) -> JetbotExportEnvelope:
        """Parse a single export envelope from a JSON string or dict."""
        if isinstance(data, str):
            data = json.loads(data)
        return self._parse_dict(data)

    # ── Query API ──────────────────────────────────────────────────────

    def get_facts(
        self,
        symbol: str | None = None,
        metric: str | None = None,
        period: str | None = None,
    ) -> List[JetbotFactRecord]:
        """Return matching fact records with optional filters."""
        self.load()
        results: List[JetbotFactRecord] = []
        for env in self._envelopes:
            for fact in env.facts:
                if symbol and fact.symbol != symbol:
                    continue
                if metric and fact.metric != metric:
                    continue
                if period and fact.period != period:
                    continue
                if fact.confidence < self.min_confidence:
                    continue
                results.append(fact)
        return results

    def get_metric(
        self,
        symbol: str,
        metric: str,
        period: str | None = None,
    ) -> Optional[float]:
        """Return the value of a single metric for a symbol, or None."""
        facts = self.get_facts(symbol=symbol, metric=metric, period=period)
        if not facts:
            return None
        # Return the highest-confidence match
        return max(facts, key=lambda f: f.confidence).value

    def get_metrics_dict(
        self,
        symbol: str,
        period: str | None = None,
    ) -> Dict[str, float]:
        """Return all core metrics for a symbol as {metric: value}."""
        facts = self.get_facts(symbol=symbol, period=period)
        result: Dict[str, float] = {}
        for fact in facts:
            if fact.metric in CORE_METRICS:
                existing = result.get(fact.metric)
                if existing is None or fact.confidence > (
                    next(
                        (f.confidence for f in facts
                         if f.metric == fact.metric and f.value == existing),
                        0.0,
                    )
                ):
                    result[fact.metric] = fact.value
        return result

    def list_symbols(self) -> List[str]:
        """Return all unique symbols across loaded envelopes."""
        self.load()
        symbols: set[str] = set()
        for env in self._envelopes:
            if env.symbol:
                symbols.add(env.symbol)
        return sorted(symbols)

    def list_periods(self) -> List[str]:
        """Return all unique periods across loaded envelopes."""
        self.load()
        periods: set[str] = set()
        for env in self._envelopes:
            if env.period:
                periods.add(env.period)
        return sorted(periods)

    # ── DataFrame integration ──────────────────────────────────────────

    def load_facts_dataframe(self) -> pd.DataFrame:
        """Return all loaded facts as a pandas DataFrame.

        Columns: symbol, company, period, period_end, metric, value, unit,
                 label, confidence, source_page, source_document
        """
        self.load()
        rows = []
        for env in self._envelopes:
            for fact in env.facts:
                if fact.confidence >= self.min_confidence:
                    rows.append({
                        "symbol": fact.symbol,
                        "company": fact.company,
                        "period": fact.period,
                        "period_end": fact.period_end,
                        "metric": fact.metric,
                        "value": fact.value,
                        "unit": fact.unit,
                        "label": fact.label,
                        "confidence": fact.confidence,
                        "source_page": fact.source_page,
                        "source_document": fact.source_document,
                        "raw_value": fact.raw_value,
                        "raw_unit": fact.raw_unit,
                        "computation": fact.computation,
                    })
        if not rows:
            return pd.DataFrame(columns=[
                "symbol", "company", "period", "period_end", "metric",
                "value", "unit", "label", "confidence", "source_page",
                "source_document", "raw_value", "raw_unit", "computation",
            ])
        return pd.DataFrame(rows)

    def build_fundamental_factors(self) -> pd.DataFrame:
        """Pivot core metrics into a wide-format DataFrame for factor analysis.

        Returns a DataFrame indexed by symbol with one column per core metric.
        For symbols with multiple periods, the latest period is used.
        """
        df = self.load_facts_dataframe()
        if df.empty:
            return pd.DataFrame(columns=list(CORE_METRICS))

        core = df[df["metric"].isin(CORE_METRICS)]
        if core.empty:
            return pd.DataFrame(columns=list(CORE_METRICS))

        # For each symbol, keep the highest-confidence value per metric
        # If multiple periods exist, prefer the latest
        result = (
            core.sort_values(["period", "confidence"], ascending=[False, False])
            .groupby(["symbol", "metric"])
            .first()
            .reset_index()
            .pivot(index="symbol", columns="metric", values="value")
        )
        # Ensure all core metrics are present as columns
        for m in CORE_METRICS:
            if m not in result.columns:
                result[m] = None
        return result[list(CORE_METRICS)]

    # ── Internal parsing ───────────────────────────────────────────────

    def _parse_file(self, path: Path) -> JetbotExportEnvelope:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return self._parse_dict(data)

    def _parse_dict(self, data: dict) -> JetbotExportEnvelope:
        version = data.get("schema_version", "1.0")
        if version not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError(f"Unsupported schema version: {version}")

        facts: List[JetbotFactRecord] = []
        symbol = data.get("symbol")
        company = data.get("company")
        period = data.get("period")
        period_end = str(data["period_end"]) if data.get("period_end") else None
        source_document = data.get("source_document")

        for f in data.get("facts", []):
            facts.append(JetbotFactRecord(
                symbol=f.get("symbol") or symbol or "",
                company=f.get("company") or company or "",
                period=f.get("period") or period or "",
                period_end=f.get("period_end") or period_end,
                metric=f["metric"],
                value=f["value"],
                unit=f.get("unit", "ratio"),
                label=f.get("label", f["metric"]),
                confidence=f.get("confidence", 0.0),
                source_page=f.get("source_page"),
                source_document=f.get("source_document") or source_document,
                raw_value=f.get("raw_value"),
                raw_unit=f.get("raw_unit"),
                computation=f.get("computation"),
            ))

        return JetbotExportEnvelope(
            doc_id=data.get("doc_id", "unknown"),
            symbol=symbol,
            company=company,
            period=period,
            period_end=period_end,
            source_document=source_document,
            facts=facts,
            risk_signals=data.get("risk_signals", []),
            metadata=data.get("metadata", {}),
            schema_version=version,
            generated_at=data.get("generated_at"),
        )


# ── Factory function ───────────────────────────────────────────────────────

def get_jetbot_facts_provider(
    export_dir: str | Path = "./jetbot_exports",
    min_confidence: float = 0.5,
) -> JetbotFactsProvider:
    """Convenience factory for creating a JetbotFactsProvider."""
    return JetbotFactsProvider(export_dir=export_dir, min_confidence=min_confidence)
