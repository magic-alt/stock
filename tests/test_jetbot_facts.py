"""Tests for the JetbotFactsProvider data source adapter."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from src.data_sources.jetbot_facts import (
    CORE_METRICS,
    JetbotExportEnvelope,
    JetbotFactRecord,
    JetbotFactsProvider,
    get_jetbot_facts_provider,
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _make_envelope(
    doc_id: str = "doc-1",
    symbol: str = "600519.SH",
    company: str = "贵州茅台",
    period: str = "2025Q4",
    facts: list[dict] | None = None,
) -> dict:
    if facts is None:
        facts = [
            {
                "metric": "revenue_growth",
                "value": 0.125,
                "unit": "ratio",
                "label": "营收增长率",
                "confidence": 0.9,
                "source_page": 42,
            },
            {
                "metric": "gross_margin",
                "value": 0.45,
                "unit": "ratio",
                "label": "毛利率",
                "confidence": 0.85,
            },
            {
                "metric": "debt_ratio",
                "value": 0.30,
                "unit": "ratio",
                "label": "资产负债率",
                "confidence": 0.88,
            },
        ]
    return {
        "schema_version": "1.0",
        "symbol": symbol,
        "company": company,
        "period": period,
        "period_end": "2025-12-31",
        "source_document": "annual.pdf",
        "doc_id": doc_id,
        "generated_at": "2026-01-01T00:00:00+00:00",
        "facts": facts,
        "risk_signals": [],
        "metadata": {"filing_type": "10-K"},
    }


@pytest.fixture
def export_dir(tmp_path: Path) -> Path:
    """Create a temp dir with two export envelopes."""
    env1 = _make_envelope(doc_id="doc-1", symbol="600519.SH", company="贵州茅台", period="2025Q4")
    env2 = _make_envelope(
        doc_id="doc-2",
        symbol="000858.SZ",
        company="五粮液",
        period="2025Q4",
        facts=[
            {
                "metric": "revenue_growth",
                "value": 0.08,
                "unit": "ratio",
                "label": "营收增长率",
                "confidence": 0.75,
            },
            {
                "metric": "debt_ratio",
                "value": 0.25,
                "unit": "ratio",
                "label": "资产负债率",
                "confidence": 0.92,
            },
        ],
    )
    (tmp_path / "doc1.json").write_text(json.dumps(env1, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "doc2.json").write_text(json.dumps(env2, ensure_ascii=False), encoding="utf-8")
    return tmp_path


# ── Loading tests ────────────────────────────────────────────────────────


class TestLoading:
    def test_load_from_directory(self, export_dir: Path) -> None:
        provider = JetbotFactsProvider(export_dir=export_dir)
        envelopes = provider.load()
        assert len(envelopes) == 2

    def test_load_missing_directory(self, tmp_path: Path) -> None:
        provider = JetbotFactsProvider(export_dir=tmp_path / "nonexistent")
        envelopes = provider.load()
        assert envelopes == []

    def test_load_caches_result(self, export_dir: Path) -> None:
        provider = JetbotFactsProvider(export_dir=export_dir)
        first = provider.load()
        second = provider.load()
        assert first is second

    def test_rescan_forces_reload(self, export_dir: Path) -> None:
        provider = JetbotFactsProvider(export_dir=export_dir)
        first = provider.load()
        second = provider.load(rescan=True)
        assert first is not second
        assert len(first) == len(second)

    def test_load_from_json_string(self) -> None:
        provider = JetbotFactsProvider(export_dir="/dev/null")
        data = _make_envelope()
        envelope = provider.load_from_json(json.dumps(data))
        assert envelope.doc_id == "doc-1"
        assert len(envelope.facts) == 3

    def test_load_from_json_dict(self) -> None:
        provider = JetbotFactsProvider(export_dir="/dev/null")
        data = _make_envelope()
        envelope = provider.load_from_json(data)
        assert envelope.doc_id == "doc-1"

    def test_unsupported_schema_version_raises(self) -> None:
        provider = JetbotFactsProvider(export_dir="/dev/null")
        data = _make_envelope()
        data["schema_version"] = "99.0"
        with pytest.raises(ValueError, match="Unsupported schema"):
            provider.load_from_json(data)


# ── Query API tests ──────────────────────────────────────────────────────


class TestQueryAPI:
    def test_get_facts_all(self, export_dir: Path) -> None:
        provider = JetbotFactsProvider(export_dir=export_dir)
        facts = provider.get_facts()
        assert len(facts) == 5  # 3 from doc1 + 2 from doc2

    def test_get_facts_by_symbol(self, export_dir: Path) -> None:
        provider = JetbotFactsProvider(export_dir=export_dir)
        facts = provider.get_facts(symbol="600519.SH")
        assert len(facts) == 3
        assert all(f.symbol == "600519.SH" for f in facts)

    def test_get_facts_by_metric(self, export_dir: Path) -> None:
        provider = JetbotFactsProvider(export_dir=export_dir)
        facts = provider.get_facts(metric="revenue_growth")
        assert len(facts) == 2

    def test_get_facts_min_confidence_filter(self, export_dir: Path) -> None:
        provider = JetbotFactsProvider(export_dir=export_dir, min_confidence=0.90)
        facts = provider.get_facts()
        # Only facts with confidence >= 0.90: revenue_growth(0.9), debt_ratio(0.92)
        assert all(f.confidence >= 0.90 for f in facts)

    def test_get_metric_returns_value(self, export_dir: Path) -> None:
        provider = JetbotFactsProvider(export_dir=export_dir)
        val = provider.get_metric("600519.SH", "revenue_growth")
        assert val == pytest.approx(0.125)

    def test_get_metric_returns_none_for_missing(self, export_dir: Path) -> None:
        provider = JetbotFactsProvider(export_dir=export_dir)
        val = provider.get_metric("600519.SH", "nonexistent_metric")
        assert val is None

    def test_get_metrics_dict(self, export_dir: Path) -> None:
        provider = JetbotFactsProvider(export_dir=export_dir)
        metrics = provider.get_metrics_dict("600519.SH")
        assert "revenue_growth" in metrics
        assert "gross_margin" in metrics
        assert "debt_ratio" in metrics

    def test_list_symbols(self, export_dir: Path) -> None:
        provider = JetbotFactsProvider(export_dir=export_dir)
        symbols = provider.list_symbols()
        assert "600519.SH" in symbols
        assert "000858.SZ" in symbols

    def test_list_periods(self, export_dir: Path) -> None:
        provider = JetbotFactsProvider(export_dir=export_dir)
        periods = provider.list_periods()
        assert "2025Q4" in periods


# ── DataFrame tests ──────────────────────────────────────────────────────


class TestDataFrame:
    def test_load_facts_dataframe(self, export_dir: Path) -> None:
        provider = JetbotFactsProvider(export_dir=export_dir)
        df = provider.load_facts_dataframe()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 5
        assert "symbol" in df.columns
        assert "metric" in df.columns
        assert "value" in df.columns

    def test_empty_dataframe_has_columns(self, tmp_path: Path) -> None:
        provider = JetbotFactsProvider(export_dir=tmp_path)
        df = provider.load_facts_dataframe()
        assert df.empty
        assert "symbol" in df.columns

    def test_build_fundamental_factors(self, export_dir: Path) -> None:
        provider = JetbotFactsProvider(export_dir=export_dir)
        df = provider.build_fundamental_factors()
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        # Should have all core metric columns
        for m in CORE_METRICS:
            assert m in df.columns
        # 600519.SH should have revenue_growth
        assert "600519.SH" in df.index


# ── Factory function ─────────────────────────────────────────────────────


class TestFactory:
    def test_get_jetbot_facts_provider(self, export_dir: Path) -> None:
        provider = get_jetbot_facts_provider(
            export_dir=export_dir,
            min_confidence=0.7,
        )
        assert isinstance(provider, JetbotFactsProvider)
        assert provider.min_confidence == 0.7
