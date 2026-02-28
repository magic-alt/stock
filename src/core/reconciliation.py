"""
Backtest vs Live Trading Reconciliation Module (V4.0-B3).

Detects performance drift between backtest simulations and live execution.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from src.core.logger import get_logger

logger = get_logger("reconciliation")


@dataclass
class ReconciliationReport:
    """Reconciliation result for a single symbol."""
    symbol: str
    backtest_pnl: float
    live_pnl: float
    pnl_drift_pct: float        # (live - backtest) / |backtest|
    fill_price_drift_pct: float # avg fill price deviation
    trade_count_diff: int       # live_count - backtest_count
    drift_causes: List[str] = field(default_factory=list)  # ["slippage", "missed_fill", ...]
    passed: bool = True         # drift within tolerance
    tolerance_pct: float = 0.05
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "backtest_pnl": round(self.backtest_pnl, 4),
            "live_pnl": round(self.live_pnl, 4),
            "pnl_drift_pct": round(self.pnl_drift_pct * 100, 2),
            "fill_price_drift_pct": round(self.fill_price_drift_pct * 100, 2),
            "trade_count_diff": self.trade_count_diff,
            "drift_causes": self.drift_causes,
            "passed": self.passed,
        }


class Reconciler:
    """
    Compare backtest results vs live trading results and detect drift.

    Usage:
        >>> r = Reconciler(tolerance_pct=0.03)
        >>> nav_cmp = r.compare_nav(backtest_nav, live_nav)
        >>> drift_dates = r.detect_drift(nav_cmp, threshold=0.02)
        >>> report = r.generate_report("600519.SH", backtest_result, live_result)
    """

    def __init__(self, tolerance_pct: float = 0.05):
        self.tolerance_pct = tolerance_pct

    def compare_nav(
        self,
        backtest_nav: pd.Series,
        live_nav: pd.Series,
    ) -> Dict[str, Any]:
        """
        Compare NAV series between backtest and live.

        Aligns on common dates, computes daily and cumulative differences.

        Returns:
            Dict with keys: daily_diff, cum_diff, max_abs_diff, aligned_bt, aligned_live
        """
        bt = backtest_nav.copy()
        lv = live_nav.copy()

        # Ensure datetime index
        bt.index = pd.to_datetime(bt.index)
        lv.index = pd.to_datetime(lv.index)

        # Align on common index, forward-fill gaps
        combined = pd.concat([bt.rename("bt"), lv.rename("lv")], axis=1)
        combined = combined.ffill().dropna()

        if combined.empty:
            return {
                "daily_diff": pd.Series(dtype=float),
                "cum_diff": pd.Series(dtype=float),
                "max_abs_diff": 0.0,
                "aligned_bt": pd.Series(dtype=float),
                "aligned_live": pd.Series(dtype=float),
            }

        aligned_bt = combined["bt"]
        aligned_lv = combined["lv"]

        # Normalize both to start at 1.0
        bt_norm = aligned_bt / aligned_bt.iloc[0]
        lv_norm = aligned_lv / aligned_lv.iloc[0]

        cum_diff = lv_norm - bt_norm
        daily_diff = (aligned_lv.pct_change() - aligned_bt.pct_change()).fillna(0)
        max_abs_diff = float(cum_diff.abs().max())

        return {
            "daily_diff": daily_diff,
            "cum_diff": cum_diff,
            "max_abs_diff": max_abs_diff,
            "aligned_bt": bt_norm,
            "aligned_live": lv_norm,
        }

    def detect_drift(
        self,
        nav_comparison: Dict[str, Any],
        threshold: float = 0.02,
    ) -> List[datetime]:
        """
        Find dates where |backtest - live| > threshold (cumulative NAV drift).

        Args:
            nav_comparison: Output from compare_nav()
            threshold: Drift threshold (e.g., 0.02 = 2% NAV divergence)

        Returns:
            List of datetime objects where drift exceeds threshold
        """
        cum_diff = nav_comparison.get("cum_diff", pd.Series(dtype=float))
        if cum_diff.empty:
            return []

        drift_mask = cum_diff.abs() > threshold
        return [dt for dt in cum_diff.index[drift_mask]]

    def compare_trades(
        self,
        backtest_trades: List[Dict[str, Any]],
        live_trades: List[Dict[str, Any]],
        symbol: Optional[str] = None,
    ) -> ReconciliationReport:
        """
        Compare trade lists between backtest and live.

        Each trade dict should have: symbol, side, price, quantity, pnl (optional)
        """
        symbol = symbol or "UNKNOWN"

        bt_trades = [t for t in backtest_trades if symbol == "UNKNOWN" or t.get("symbol") == symbol]
        lv_trades = [t for t in live_trades if symbol == "UNKNOWN" or t.get("symbol") == symbol]

        bt_pnl = sum(t.get("pnl", 0) for t in bt_trades)
        lv_pnl = sum(t.get("pnl", 0) for t in lv_trades)

        pnl_drift = (lv_pnl - bt_pnl) / abs(bt_pnl) if abs(bt_pnl) > 1e-9 else 0.0

        # Fill price drift
        bt_prices = [t.get("price", 0) for t in bt_trades if t.get("price")]
        lv_prices = [t.get("price", 0) for t in lv_trades if t.get("price")]

        avg_bt_price = np.mean(bt_prices) if bt_prices else 0.0
        avg_lv_price = np.mean(lv_prices) if lv_prices else 0.0

        price_drift = (avg_lv_price - avg_bt_price) / avg_bt_price if avg_bt_price > 1e-9 else 0.0

        trade_count_diff = len(lv_trades) - len(bt_trades)

        # Identify likely causes
        causes = []
        if abs(price_drift) > 0.001:
            causes.append("slippage")
        if trade_count_diff < 0:
            causes.append("missed_fill")
        if trade_count_diff > 0:
            causes.append("extra_fill")
        if abs(pnl_drift) > self.tolerance_pct and not causes:
            causes.append("commission_diff")

        passed = abs(pnl_drift) <= self.tolerance_pct

        return ReconciliationReport(
            symbol=symbol,
            backtest_pnl=bt_pnl,
            live_pnl=lv_pnl,
            pnl_drift_pct=pnl_drift,
            fill_price_drift_pct=price_drift,
            trade_count_diff=trade_count_diff,
            drift_causes=causes,
            passed=passed,
            tolerance_pct=self.tolerance_pct,
        )

    def generate_report(
        self,
        symbol: str,
        backtest_result: Dict[str, Any],
        live_result: Dict[str, Any],
    ) -> ReconciliationReport:
        """
        Generate a comprehensive reconciliation report.

        Args:
            symbol: Symbol identifier
            backtest_result: Dict with keys: pnl, trades, nav_series
            live_result: Dict with keys: pnl, trades, nav_series
        """
        bt_trades = backtest_result.get("trades", [])
        lv_trades = live_result.get("trades", [])

        report = self.compare_trades(bt_trades, lv_trades, symbol=symbol)

        # Override PnL if directly provided
        if "pnl" in backtest_result and "pnl" in live_result:
            bt_pnl = float(backtest_result["pnl"])
            lv_pnl = float(live_result["pnl"])
            pnl_drift = (lv_pnl - bt_pnl) / abs(bt_pnl) if abs(bt_pnl) > 1e-9 else 0.0
            report.backtest_pnl = bt_pnl
            report.live_pnl = lv_pnl
            report.pnl_drift_pct = pnl_drift
            report.passed = abs(pnl_drift) <= self.tolerance_pct

        return report

    def run_batch(
        self,
        symbols: List[str],
        backtest_results: Dict[str, Dict[str, Any]],
        live_results: Dict[str, Dict[str, Any]],
    ) -> List[ReconciliationReport]:
        """
        Run reconciliation for multiple symbols.

        Args:
            symbols: List of symbols
            backtest_results: {symbol: result_dict}
            live_results: {symbol: result_dict}

        Returns:
            List of ReconciliationReport, one per symbol
        """
        reports = []
        for sym in symbols:
            bt = backtest_results.get(sym, {})
            lv = live_results.get(sym, {})
            try:
                report = self.generate_report(sym, bt, lv)
                reports.append(report)
            except Exception as e:
                logger.error(f"Reconciliation failed for {sym}: {e}")
                reports.append(ReconciliationReport(
                    symbol=sym,
                    backtest_pnl=0.0,
                    live_pnl=0.0,
                    pnl_drift_pct=0.0,
                    fill_price_drift_pct=0.0,
                    trade_count_diff=0,
                    drift_causes=["reconciliation_error"],
                    passed=False,
                ))
        return reports


__all__ = ["Reconciler", "ReconciliationReport"]
