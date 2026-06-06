"""Tests for the fundamental filter strategy using jetbot exports."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src.data_sources.jetbot_facts import JetbotFactsProvider
from src.strategies.fundamental_filter import (
    FilterResult,
    FundamentalFilter,
    FundamentalThresholds,
    create_fundamental_filter,
    score_symbols_from_exports,
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _make_envelope(
    doc_id: str,
    symbol: str,
    company: str,
    facts: list[dict],
    period: str = "2025Q4",
) -> dict:
    return {
        "schema_version": "1.0",
        "symbol": symbol,
        "company": company,
        "period": period,
        "period_end": "2025-12-31",
        "source_document": f"{doc_id}.pdf",
        "doc_id": doc_id,
        "generated_at": "2026-01-01T00:00:00+00:00",
        "facts": facts,
        "risk_signals": [],
        "metadata": {},
    }


def _fact(metric: str, value: float, confidence: float = 0.9) -> dict:
    return {
        "metric": metric,
        "value": value,
        "unit": "ratio",
        "label": metric.replace("_", " ").title(),
        "confidence": confidence,
    }


@pytest.fixture
def export_dir(tmp_path: Path) -> Path:
    """Create exports for 3 symbols with different fundamentals."""
    # Good company: all metrics pass
    good = _make_envelope("doc-1", "GOOD.SH", "好公司", [
        _fact("revenue_growth", 0.15),
        _fact("net_profit_growth", 0.20),
        _fact("gross_margin", 0.45),
        _fact("operating_cash_flow", 500_000_000),
        _fact("debt_ratio", 0.35),
    ])
    # Bad company: negative growth, high leverage
    bad = _make_envelope("doc-2", "BAD.SH", "差公司", [
        _fact("revenue_growth", -0.10),
        _fact("net_profit_growth", -0.25),
        _fact("gross_margin", 0.05),
        _fact("operating_cash_flow", -100_000_000),
        _fact("debt_ratio", 0.85),
    ])
    # Partial company: only some metrics available
    partial = _make_envelope("doc-3", "PART.SZ", "部分公司", [
        _fact("revenue_growth", 0.08),
        _fact("gross_margin", 0.30),
    ])
    (tmp_path / "good.json").write_text(json.dumps(good, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "bad.json").write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "partial.json").write_text(json.dumps(partial, ensure_ascii=False), encoding="utf-8")
    return tmp_path


# ── Threshold configuration tests ────────────────────────────────────────


class TestFundamentalThresholds:
    def test_default_bounds(self) -> None:
        t = FundamentalThresholds()
        assert t.revenue_growth_min == 0.0
        assert t.gross_margin_min == 0.10
        assert t.debt_ratio_max == 0.70

    def test_get_bounds(self) -> None:
        t = FundamentalThresholds()
        lo, hi = t.get_bounds("revenue_growth")
        assert lo == 0.0
        assert hi is None

    def test_custom_bounds(self) -> None:
        t = FundamentalThresholds(revenue_growth_min=0.05, debt_ratio_max=0.50)
        assert t.revenue_growth_min == 0.05
        assert t.debt_ratio_max == 0.50

    def test_unknown_metric_returns_none_bounds(self) -> None:
        t = FundamentalThresholds()
        lo, hi = t.get_bounds("unknown_metric")
        assert lo is None
        assert hi is None


# ── Filter scoring tests ────────────────────────────────────────────────


class TestFundamentalFilter:
    def test_good_company_passes(self, export_dir: Path) -> None:
        provider = JetbotFactsProvider(export_dir=export_dir)
        filt = FundamentalFilter(provider)
        result = filt.score_symbol("GOOD.SH")
        assert result.passed is True
        assert result.score > 0.8
        assert result.symbol == "GOOD.SH"

    def test_bad_company_fails(self, export_dir: Path) -> None:
        provider = JetbotFactsProvider(export_dir=export_dir)
        filt = FundamentalFilter(provider)
        result = filt.score_symbol("BAD.SH")
        assert result.passed is False
        assert result.score < 1.0

    def test_partial_company_passes_when_not_require_all(self, export_dir: Path) -> None:
        provider = JetbotFactsProvider(export_dir=export_dir)
        thresholds = FundamentalThresholds(require_all=False)
        filt = FundamentalFilter(provider, thresholds)
        result = filt.score_symbol("PART.SZ")
        # With only 2 metrics that pass, and require_all=False, should pass
        assert result.passed is True

    def test_partial_company_fails_when_require_all(self, export_dir: Path) -> None:
        provider = JetbotFactsProvider(export_dir=export_dir)
        thresholds = FundamentalThresholds(require_all=True)
        filt = FundamentalFilter(provider, thresholds)
        result = filt.score_symbol("PART.SZ")
        # require_all=True means missing metrics cause failure
        assert result.passed is False

    def test_score_all_sorted(self, export_dir: Path) -> None:
        provider = JetbotFactsProvider(export_dir=export_dir)
        filt = FundamentalFilter(provider)
        results = filt.score_all()
        assert len(results) == 3
        # Should be sorted by score descending
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_filter_passed(self, export_dir: Path) -> None:
        provider = JetbotFactsProvider(export_dir=export_dir)
        filt = FundamentalFilter(provider)
        passed = filt.filter_passed()
        assert "GOOD.SH" in passed
        assert "BAD.SH" not in passed

    def test_filter_dataframe(self, export_dir: Path) -> None:
        provider = JetbotFactsProvider(export_dir=export_dir)
        filt = FundamentalFilter(provider)
        df = pd.DataFrame({
            "symbol": ["GOOD.SH", "BAD.SH", "PART.SZ"],
            "close": [100.0, 50.0, 75.0],
        })
        filtered = filt.filter_dataframe(df)
        assert "GOOD.SH" in filtered["symbol"].values
        assert "BAD.SH" not in filtered["symbol"].values

    def test_filter_dataframe_empty_when_none_pass(self, tmp_path: Path) -> None:
        # Create an export with all bad metrics
        bad = _make_envelope("doc-1", "BAD.SH", "差公司", [
            _fact("revenue_growth", -0.50),
            _fact("debt_ratio", 0.95),
        ])
        (tmp_path / "bad.json").write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
        provider = JetbotFactsProvider(export_dir=tmp_path)
        filt = FundamentalFilter(provider)
        df = pd.DataFrame({"symbol": ["BAD.SH"], "close": [50.0]})
        filtered = filt.filter_dataframe(df)
        assert filtered.empty


# ── FilterResult tests ───────────────────────────────────────────────────


class TestFilterResult:
    def test_summary_pass(self) -> None:
        r = FilterResult(symbol="X.SH", passed=True, score=0.95)
        assert "PASS" in r.summary()

    def test_summary_fail(self) -> None:
        r = FilterResult(symbol="X.SH", passed=False, score=0.30)
        assert "FAIL" in r.summary()


# ── Custom weights test ──────────────────────────────────────────────────


class TestCustomWeights:
    def test_weighted_scoring(self, export_dir: Path) -> None:
        provider = JetbotFactsProvider(export_dir=export_dir)
        weights = {
            "revenue_growth": 3.0,
            "net_profit_growth": 1.0,
            "gross_margin": 1.0,
            "operating_cash_flow": 1.0,
            "debt_ratio": 1.0,
        }
        filt = FundamentalFilter(provider, weights=weights)
        result = filt.score_symbol("GOOD.SH")
        assert result.passed is True
        assert result.score > 0.0


# ── Convenience functions ────────────────────────────────────────────────


class TestConvenienceFunctions:
    def test_create_fundamental_filter(self, export_dir: Path) -> None:
        filt = create_fundamental_filter(
            export_dir=str(export_dir),
            min_confidence=0.5,
            gross_margin_min=0.20,
        )
        assert isinstance(filt, FundamentalFilter)
        assert filt.thresholds.gross_margin_min == 0.20

    def test_score_symbols_from_exports(self, export_dir: Path) -> None:
        results = score_symbols_from_exports(export_dir=str(export_dir))
        assert len(results) > 0
        assert all(isinstance(r, FilterResult) for r in results)
