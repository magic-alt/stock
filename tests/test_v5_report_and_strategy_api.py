"""
Tests for V5.0-A: Interactive report generator and Strategy API.
"""
from __future__ import annotations

import json
import os
import tempfile

import numpy as np
import pandas as pd
import pytest

try:
    import jinja2  # noqa: F401
    _HAS_JINJA2 = True
except ImportError:
    _HAS_JINJA2 = False


# ---------------------------------------------------------------------------
# A-2: InteractiveReportGenerator tests
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _HAS_JINJA2, reason="jinja2 not installed")
class TestReportGenerator:
    """Tests for src/backtest/report_generator.py."""

    def _make_nav(self, days: int = 100, start_val: float = 1.0) -> pd.Series:
        rng = pd.date_range("2024-01-01", periods=days, freq="B")
        returns = np.random.default_rng(42).normal(0.0005, 0.015, size=days)
        nav = start_val * np.cumprod(1 + returns)
        return pd.Series(nav, index=rng, name="nav")

    def _make_metrics(self) -> dict:
        return {
            "strategy": "macd",
            "cum_return": 0.15,
            "ann_return": 0.18,
            "ann_vol": 0.22,
            "sharpe": 0.82,
            "mdd": 0.12,
            "calmar": 1.5,
            "win_rate": 0.55,
            "trades": 42,
            "profit_factor": 1.3,
            "expectancy": 0.005,
            "var_95": -0.02,
            "var_99": -0.04,
            "cvar_95": -0.025,
            "cvar_99": -0.05,
        }

    def test_generate_returns_html(self):
        from src.backtest.report_generator import InteractiveReportGenerator
        gen = InteractiveReportGenerator()
        nav = self._make_nav()
        metrics = self._make_metrics()
        html = gen.generate(metrics, nav=nav)
        assert "<!DOCTYPE html>" in html
        assert "macd" in html
        assert "Performance Overview" in html

    def test_generate_with_dark_theme(self):
        from src.backtest.report_generator import InteractiveReportGenerator, ReportConfig
        gen = InteractiveReportGenerator(ReportConfig(theme="dark"))
        html = gen.generate(self._make_metrics(), nav=self._make_nav())
        assert "#1a1a2e" in html

    def test_generate_with_light_theme(self):
        from src.backtest.report_generator import InteractiveReportGenerator, ReportConfig
        gen = InteractiveReportGenerator(ReportConfig(theme="light"))
        html = gen.generate(self._make_metrics(), nav=self._make_nav())
        assert "#ffffff" in html

    def test_save_creates_file(self):
        from src.backtest.report_generator import InteractiveReportGenerator
        gen = InteractiveReportGenerator()
        nav = self._make_nav()
        metrics = self._make_metrics()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "report.html")
            result = gen.save(metrics, path, nav=nav)
            assert os.path.exists(result)
            with open(result, encoding="utf-8") as f:
                content = f.read()
            assert "<!DOCTYPE html>" in content

    def test_nav_extracted_from_metrics(self):
        from src.backtest.report_generator import InteractiveReportGenerator
        gen = InteractiveReportGenerator()
        metrics = self._make_metrics()
        metrics["nav"] = self._make_nav()
        html = gen.generate(metrics)
        assert "Performance Overview" in html

    def test_empty_nav_returns_fallback(self):
        from src.backtest.report_generator import InteractiveReportGenerator
        gen = InteractiveReportGenerator()
        html = gen.generate({"strategy": "test"})
        assert "No NAV data" in html

    def test_benchmark_chart_included(self):
        from src.backtest.report_generator import InteractiveReportGenerator
        gen = InteractiveReportGenerator()
        nav = self._make_nav()
        bench = self._make_nav(days=100, start_val=1.0)
        bench.index = nav.index  # align
        metrics = self._make_metrics()
        metrics["bench_return"] = 0.10
        metrics["excess_return"] = 0.05
        html = gen.generate(metrics, nav=nav, benchmark_nav=bench)
        assert "Benchmark" in html

    def test_drawdown_section_present(self):
        from src.backtest.report_generator import InteractiveReportGenerator
        gen = InteractiveReportGenerator()
        html = gen.generate(self._make_metrics(), nav=self._make_nav())
        assert "Drawdown" in html

    def test_monthly_returns_section(self):
        from src.backtest.report_generator import InteractiveReportGenerator
        gen = InteractiveReportGenerator()
        nav = self._make_nav(days=252)
        html = gen.generate(self._make_metrics(), nav=nav)
        assert "Monthly Returns" in html

    def test_risk_metrics_section(self):
        from src.backtest.report_generator import InteractiveReportGenerator
        gen = InteractiveReportGenerator()
        html = gen.generate(self._make_metrics(), nav=self._make_nav())
        assert "Risk Metrics" in html
        assert "VaR" in html

    def test_no_drawdown_when_disabled(self):
        from src.backtest.report_generator import InteractiveReportGenerator, ReportConfig
        gen = InteractiveReportGenerator(ReportConfig(include_drawdown=False))
        html = gen.generate(self._make_metrics(), nav=self._make_nav())
        assert "dd-chart" not in html

    def test_grid_report_generation(self):
        from src.backtest.report_generator import InteractiveReportGenerator
        gen = InteractiveReportGenerator()
        df = pd.DataFrame({
            "fast": [5, 10, 15],
            "slow": [20, 30, 40],
            "cum_return": [0.1, 0.2, -0.05],
            "sharpe": [0.5, 1.2, -0.3],
            "mdd": [0.05, 0.08, 0.15],
            "trades": [10, 20, 5],
        })
        html = gen.generate_grid_report(df)
        assert "3 configurations" in html
        assert "fast" in html

    def test_grid_report_save(self):
        from src.backtest.report_generator import InteractiveReportGenerator
        gen = InteractiveReportGenerator()
        df = pd.DataFrame({"x": [1], "cum_return": [0.1], "sharpe": [1.0]})
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "grid.html")
            result = gen.save_grid_report(df, path)
            assert os.path.exists(result)

    def test_extra_sections(self):
        from src.backtest.report_generator import InteractiveReportGenerator, ReportSection
        gen = InteractiveReportGenerator()
        section = ReportSection(title="Custom Section", html="<p>Hello</p>")
        html = gen.generate(self._make_metrics(), nav=self._make_nav(), extra_sections=[section])
        assert "Custom Section" in html
        assert "<p>Hello</p>" in html


# ---------------------------------------------------------------------------
# A-2: Chart data builder unit tests
# ---------------------------------------------------------------------------

class TestChartDataBuilders:

    def test_build_nav_chart_data(self):
        from src.backtest.report_generator import _build_nav_chart_data
        nav = pd.Series([1.0, 1.05, 1.03], index=pd.date_range("2024-01-01", periods=3))
        result = _build_nav_chart_data(nav)
        assert len(result["dates"]) == 3
        assert len(result["values"]) == 3
        assert result["dates"][0] == "2024-01-01"

    def test_build_drawdown_data(self):
        from src.backtest.report_generator import _build_drawdown_data
        nav = pd.Series([1.0, 1.1, 0.9, 1.0], index=pd.date_range("2024-01-01", periods=4))
        result = _build_drawdown_data(nav)
        assert len(result["dates"]) == 4
        assert result["values"][0] == 0.0
        assert result["values"][2] < 0  # drawdown at 0.9

    def test_build_monthly_returns(self):
        from src.backtest.report_generator import _build_monthly_returns
        nav = pd.Series(
            np.linspace(1.0, 1.2, 252),
            index=pd.date_range("2024-01-01", periods=252, freq="B"),
        )
        months = _build_monthly_returns(nav)
        assert len(months) > 0
        assert "year" in months[0]
        assert "month" in months[0]
        assert "return" in months[0]

    def test_benchmark_chart_none_bench(self):
        from src.backtest.report_generator import _build_benchmark_chart_data
        nav = pd.Series([1.0, 1.1], index=pd.date_range("2024-01-01", periods=2))
        assert _build_benchmark_chart_data(nav, None) is None

    def test_benchmark_chart_with_bench(self):
        from src.backtest.report_generator import _build_benchmark_chart_data
        idx = pd.date_range("2024-01-01", periods=3)
        nav = pd.Series([1.0, 1.1, 1.2], index=idx)
        bench = pd.Series([1.0, 1.05, 1.08], index=idx)
        result = _build_benchmark_chart_data(nav, bench)
        assert result is not None
        assert len(result["strategy"]) == 3
        assert len(result["benchmark"]) == 3


# ---------------------------------------------------------------------------
# A-3: Strategy API tests
# ---------------------------------------------------------------------------

class TestStrategyAPI:
    """Tests for src/platform/api/strategy_api.py."""

    def test_list_strategies(self):
        from src.platform.api.strategy_api import strategy_router
        from src.platform.api.router import RequestContext
        resp = strategy_router.dispatch(RequestContext(method="GET", path="/api/v2/strategies"))
        assert resp.status_code == 200
        assert resp.body["ok"] is True
        assert resp.body["count"] > 0
        assert len(resp.body["strategies"]) > 0

    def test_get_strategy_found(self):
        from src.platform.api.strategy_api import strategy_router
        from src.platform.api.router import RequestContext
        resp = strategy_router.dispatch(RequestContext(method="GET", path="/api/v2/strategies/macd"))
        assert resp.status_code == 200
        assert resp.body["ok"] is True
        assert resp.body["strategy"]["name"] == "macd"

    def test_get_strategy_not_found(self):
        from src.platform.api.strategy_api import strategy_router
        from src.platform.api.router import RequestContext
        resp = strategy_router.dispatch(RequestContext(method="GET", path="/api/v2/strategies/nonexistent_xyz"))
        assert resp.status_code == 404

    def test_get_template(self):
        from src.platform.api.strategy_api import strategy_router
        from src.platform.api.router import RequestContext
        resp = strategy_router.dispatch(RequestContext(method="GET", path="/api/v2/strategies/templates/macd"))
        assert resp.status_code == 200
        assert "template" in resp.body
        assert "class My" in resp.body["template"]

    def test_get_template_not_found(self):
        from src.platform.api.strategy_api import strategy_router
        from src.platform.api.router import RequestContext
        resp = strategy_router.dispatch(RequestContext(method="GET", path="/api/v2/strategies/templates/nonexistent_xyz"))
        assert resp.status_code == 404

    def test_validate_valid_code(self):
        from src.platform.api.strategy_api import strategy_router
        from src.platform.api.router import RequestContext
        code = "import backtrader as bt\nclass MyStrategy(bt.Strategy):\n    pass\n"
        resp = strategy_router.dispatch(RequestContext(
            method="POST", path="/api/v2/strategies/validate",
            body={"code": code},
        ))
        assert resp.status_code == 200
        assert resp.body["valid"] is True

    def test_validate_syntax_error(self):
        from src.platform.api.strategy_api import strategy_router
        from src.platform.api.router import RequestContext
        code = "def broken(:\n    pass\n"
        resp = strategy_router.dispatch(RequestContext(
            method="POST", path="/api/v2/strategies/validate",
            body={"code": code},
        ))
        assert resp.status_code == 200
        assert resp.body["valid"] is False
        assert any(e["severity"] == "error" for e in resp.body["errors"])

    def test_validate_restricted_import(self):
        from src.platform.api.strategy_api import strategy_router
        from src.platform.api.router import RequestContext
        code = "import os\nimport subprocess\n"
        resp = strategy_router.dispatch(RequestContext(
            method="POST", path="/api/v2/strategies/validate",
            body={"code": code},
        ))
        assert resp.status_code == 200
        assert len(resp.body["errors"]) >= 2
        assert all(e["severity"] == "warning" for e in resp.body["errors"])

    def test_validate_empty_code(self):
        from src.platform.api.strategy_api import strategy_router
        from src.platform.api.router import RequestContext
        resp = strategy_router.dispatch(RequestContext(
            method="POST", path="/api/v2/strategies/validate",
            body={"code": ""},
        ))
        assert resp.status_code == 400

    def test_run_missing_strategy(self):
        from src.platform.api.strategy_api import strategy_router
        from src.platform.api.router import RequestContext
        resp = strategy_router.dispatch(RequestContext(
            method="POST", path="/api/v2/strategies/run",
            body={},
        ))
        assert resp.status_code == 400

    def test_run_missing_symbols(self):
        from src.platform.api.strategy_api import strategy_router
        from src.platform.api.router import RequestContext
        resp = strategy_router.dispatch(RequestContext(
            method="POST", path="/api/v2/strategies/run",
            body={"strategy": "macd"},
        ))
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Metric formatting tests
# ---------------------------------------------------------------------------

class TestMetricFormatting:

    def test_fmt_pct(self):
        from src.backtest.report_generator import _fmt_pct
        assert _fmt_pct(0.1523) == "15.23%"
        assert _fmt_pct(float("nan")) == "N/A"
        assert _fmt_pct(float("inf")) == "N/A"

    def test_fmt_num(self):
        from src.backtest.report_generator import _fmt_num
        assert _fmt_num(1.2345) == "1.2345"
        assert _fmt_num(float("nan")) == "N/A"

    def test_fmt_int(self):
        from src.backtest.report_generator import _fmt_int
        assert _fmt_int(42.0) == "42"
        assert _fmt_int(float("nan")) == "N/A"
