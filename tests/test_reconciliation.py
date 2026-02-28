"""
Tests for src/core/reconciliation.py — Reconciler and ReconciliationReport.
"""
from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from src.core.reconciliation import Reconciler, ReconciliationReport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_nav(seed: int, n: int = 100) -> pd.Series:
    rng = np.random.RandomState(seed)
    returns = rng.randn(n) * 0.01
    return pd.Series(
        (1 + returns).cumprod(),
        index=pd.date_range("2024-01-01", periods=n),
    )


def _make_trades(n: int = 10, seed: int = 0, pnl_per_trade: float = 10.0) -> list:
    rng = np.random.RandomState(seed)
    trades = []
    for i in range(n):
        trades.append({
            "symbol": "600519.SH",
            "side": "buy" if i % 2 == 0 else "sell",
            "price": 100.0 + rng.uniform(-2, 2),
            "quantity": 100,
            "pnl": pnl_per_trade,
        })
    return trades


# ---------------------------------------------------------------------------
# Tests: compare_nav
# ---------------------------------------------------------------------------

class TestCompareNav:
    def test_perfect_match_max_diff_is_zero(self):
        nav = _make_nav(seed=1)
        r = Reconciler()
        result = r.compare_nav(nav, nav.copy())
        assert result["max_abs_diff"] == pytest.approx(0.0, abs=1e-12)

    def test_compare_nav_returns_required_keys(self):
        nav = _make_nav(seed=2)
        r = Reconciler()
        result = r.compare_nav(nav, nav * 1.01)
        for key in ("daily_diff", "cum_diff", "max_abs_diff", "aligned_bt", "aligned_live"):
            assert key in result

    def test_compare_nav_normalised_start_at_one(self):
        bt = _make_nav(seed=3)
        lv = _make_nav(seed=4)
        r = Reconciler()
        result = r.compare_nav(bt, lv)
        assert result["aligned_bt"].iloc[0] == pytest.approx(1.0)
        assert result["aligned_live"].iloc[0] == pytest.approx(1.0)

    def test_compare_nav_different_series_produces_nonzero_diff(self):
        bt = _make_nav(seed=5)
        lv = _make_nav(seed=6)
        r = Reconciler()
        result = r.compare_nav(bt, lv)
        assert result["max_abs_diff"] > 0

    def test_compare_nav_empty_series_returns_empty(self):
        r = Reconciler()
        empty = pd.Series(dtype=float)
        result = r.compare_nav(empty, empty.copy())
        assert result["max_abs_diff"] == pytest.approx(0.0)
        assert len(result["cum_diff"]) == 0

    def test_compare_nav_date_alignment(self):
        """Live NAV covering only a subset of backtest dates should still work."""
        bt = _make_nav(seed=1, n=50)
        lv = bt.iloc[10:40].copy()  # shorter window
        r = Reconciler()
        result = r.compare_nav(bt, lv)
        # After alignment there must be rows
        assert len(result["cum_diff"]) > 0


# ---------------------------------------------------------------------------
# Tests: detect_drift
# ---------------------------------------------------------------------------

class TestDetectDrift:
    def test_perfect_match_no_drift_dates(self):
        nav = _make_nav(seed=10)
        r = Reconciler()
        cmp = r.compare_nav(nav, nav.copy())
        dates = r.detect_drift(cmp, threshold=0.01)
        assert len(dates) == 0

    def test_large_divergence_detected(self):
        # Create two genuinely diverging series (opposite drifts)
        dates = pd.date_range("2024-01-01", periods=100)
        bt = pd.Series((1 + np.full(100, 0.001)).cumprod(), index=dates)
        lv = pd.Series((1 + np.full(100, -0.001)).cumprod(), index=dates)
        # After normalization bt_norm grows, lv_norm falls → diff ~10% after 50 days
        r = Reconciler()
        cmp = r.compare_nav(bt, lv)
        dates_drifted = r.detect_drift(cmp, threshold=0.02)
        assert len(dates_drifted) > 0

    def test_drift_dates_are_datetime(self):
        bt = _make_nav(seed=12)
        lv = bt * 1.05
        r = Reconciler()
        cmp = r.compare_nav(bt, lv)
        dates = r.detect_drift(cmp, threshold=0.01)
        for d in dates:
            assert isinstance(d, (datetime, pd.Timestamp))

    def test_empty_comparison_returns_empty(self):
        r = Reconciler()
        empty_cmp = {"cum_diff": pd.Series(dtype=float)}
        dates = r.detect_drift(empty_cmp, threshold=0.01)
        assert dates == []


# ---------------------------------------------------------------------------
# Tests: compare_trades
# ---------------------------------------------------------------------------

class TestCompareTrades:
    def test_perfect_match_passes(self):
        bt = _make_trades(n=10, pnl_per_trade=100.0)
        r = Reconciler(tolerance_pct=0.05)
        report = r.compare_trades(bt, list(bt), symbol="600519.SH")
        assert report.passed is True
        assert report.pnl_drift_pct == pytest.approx(0.0)

    def test_small_drift_within_tolerance(self):
        bt = _make_trades(n=10, pnl_per_trade=1000.0)
        lv = _make_trades(n=10, pnl_per_trade=1020.0)  # 2 % better
        r = Reconciler(tolerance_pct=0.05)
        report = r.compare_trades(bt, lv, symbol="600519.SH")
        assert report.passed is True

    def test_large_drift_fails(self):
        bt = _make_trades(n=10, pnl_per_trade=1000.0)
        lv = _make_trades(n=10, pnl_per_trade=800.0)  # 20 % worse
        r = Reconciler(tolerance_pct=0.05)
        report = r.compare_trades(bt, lv, symbol="600519.SH")
        assert report.passed is False

    def test_trade_count_diff_less_live(self):
        bt = _make_trades(n=12)
        lv = _make_trades(n=10)
        r = Reconciler()
        report = r.compare_trades(bt, lv, symbol="600519.SH")
        assert report.trade_count_diff == -2

    def test_trade_count_diff_more_live(self):
        bt = _make_trades(n=5)
        lv = _make_trades(n=8)
        r = Reconciler()
        report = r.compare_trades(bt, lv, symbol="600519.SH")
        assert report.trade_count_diff == 3

    def test_missed_fill_cause_detected(self):
        bt = _make_trades(n=10)
        lv = _make_trades(n=7)
        r = Reconciler()
        report = r.compare_trades(bt, lv, symbol="600519.SH")
        assert "missed_fill" in report.drift_causes

    def test_extra_fill_cause_detected(self):
        bt = _make_trades(n=5)
        lv = _make_trades(n=8)
        r = Reconciler()
        report = r.compare_trades(bt, lv, symbol="600519.SH")
        assert "extra_fill" in report.drift_causes

    def test_slippage_cause_detected(self):
        bt = [{"symbol": "S", "price": 100.0, "quantity": 100, "pnl": 0}]
        lv = [{"symbol": "S", "price": 100.5, "quantity": 100, "pnl": 0}]
        r = Reconciler()
        report = r.compare_trades(bt, lv, symbol="S")
        assert "slippage" in report.drift_causes

    def test_report_is_reconciliation_report_instance(self):
        r = Reconciler()
        report = r.compare_trades([], [], symbol="X")
        assert isinstance(report, ReconciliationReport)

    def test_backtest_pnl_zero_no_crash(self):
        bt = [{"symbol": "Z", "price": 100.0, "quantity": 10, "pnl": 0.0}]
        lv = [{"symbol": "Z", "price": 100.0, "quantity": 10, "pnl": 5.0}]
        r = Reconciler()
        report = r.compare_trades(bt, lv, symbol="Z")
        # bt_pnl == 0 → drift should be 0 (guarded by |bt_pnl| > 1e-9)
        assert report.pnl_drift_pct == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Tests: generate_report
# ---------------------------------------------------------------------------

class TestGenerateReport:
    def test_generate_report_uses_direct_pnl(self):
        r = Reconciler(tolerance_pct=0.05)
        report = r.generate_report(
            "600519.SH",
            backtest_result={"pnl": 10000.0, "trades": []},
            live_result={"pnl": 9600.0, "trades": []},  # -4 % drift
        )
        assert report.passed is True  # within 5 %
        assert report.backtest_pnl == pytest.approx(10000.0)

    def test_generate_report_fails_outside_tolerance(self):
        r = Reconciler(tolerance_pct=0.05)
        report = r.generate_report(
            "600519.SH",
            backtest_result={"pnl": 10000.0, "trades": []},
            live_result={"pnl": 9000.0, "trades": []},  # -10 % drift
        )
        assert report.passed is False

    def test_generate_report_falls_back_to_trade_pnl(self):
        """Without direct 'pnl' key, falls back to summing trade pnls."""
        bt_trades = [{"symbol": "A", "pnl": 500.0}, {"symbol": "A", "pnl": 500.0}]
        lv_trades = [{"symbol": "A", "pnl": 510.0}, {"symbol": "A", "pnl": 490.0}]
        r = Reconciler()
        report = r.generate_report("A", {"trades": bt_trades}, {"trades": lv_trades})
        assert report.backtest_pnl == pytest.approx(1000.0)

    def test_generate_report_symbol_set(self):
        r = Reconciler()
        report = r.generate_report("TEST.SH", {"pnl": 100, "trades": []}, {"pnl": 100, "trades": []})
        assert report.symbol == "TEST.SH"


# ---------------------------------------------------------------------------
# Tests: run_batch
# ---------------------------------------------------------------------------

class TestRunBatch:
    def test_batch_reconciliation_length(self):
        r = Reconciler()
        symbols = ["A", "B", "C"]
        bt = {s: {"pnl": 1000, "trades": []} for s in symbols}
        lv = {s: {"pnl": 1000, "trades": []} for s in symbols}
        reports = r.run_batch(symbols, bt, lv)
        assert len(reports) == 3

    def test_batch_all_pass_when_identical(self):
        r = Reconciler()
        symbols = ["X", "Y"]
        bt = {s: {"pnl": 500.0, "trades": []} for s in symbols}
        lv = dict(bt)
        reports = r.run_batch(symbols, bt, lv)
        assert all(rep.passed for rep in reports)

    def test_batch_handles_missing_symbol_gracefully(self):
        """Symbol in list but not in backtest_results → should not raise."""
        r = Reconciler()
        symbols = ["KNOWN", "UNKNOWN"]
        bt = {"KNOWN": {"pnl": 200.0, "trades": []}}
        lv = {"KNOWN": {"pnl": 200.0, "trades": []}}
        reports = r.run_batch(symbols, bt, lv)
        assert len(reports) == 2

    def test_batch_returns_reconciliation_reports(self):
        r = Reconciler()
        reports = r.run_batch(["Z"], {"Z": {"pnl": 1.0}}, {"Z": {"pnl": 1.0}})
        assert all(isinstance(rep, ReconciliationReport) for rep in reports)


# ---------------------------------------------------------------------------
# Tests: ReconciliationReport.to_dict
# ---------------------------------------------------------------------------

class TestReconciliationReportToDict:
    def test_to_dict_contains_required_fields(self):
        report = ReconciliationReport(
            symbol="600519.SH",
            backtest_pnl=5000.0,
            live_pnl=4900.0,
            pnl_drift_pct=-0.02,
            fill_price_drift_pct=0.001,
            trade_count_diff=0,
            passed=True,
        )
        d = report.to_dict()
        for key in ("symbol", "backtest_pnl", "live_pnl", "pnl_drift_pct",
                    "fill_price_drift_pct", "trade_count_diff", "passed"):
            assert key in d

    def test_to_dict_pnl_drift_is_percentage(self):
        report = ReconciliationReport(
            symbol="X",
            backtest_pnl=1000.0,
            live_pnl=980.0,
            pnl_drift_pct=-0.02,
            fill_price_drift_pct=0.0,
            trade_count_diff=0,
            passed=True,
        )
        d = report.to_dict()
        assert d["pnl_drift_pct"] == pytest.approx(-2.0)  # stored as percentage
