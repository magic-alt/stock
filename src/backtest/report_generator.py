"""
Interactive Backtest Report Generator (V5.0-A-2)

Generates self-contained interactive HTML reports from backtest results.
Uses Jinja2 templates with inline ECharts for zero-dependency viewing.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from src.core.logger import get_logger

logger = get_logger("backtest.report")

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ReportSection:
    """A named section within an interactive report."""
    title: str
    html: str
    order: int = 0


@dataclass
class ReportConfig:
    """Configuration for report generation."""
    title: str = "Backtest Report"
    theme: str = "dark"  # "dark" | "light"
    include_trades: bool = True
    include_drawdown: bool = True
    include_monthly: bool = True
    include_risk: bool = True
    locale: str = "zh-CN"


# ---------------------------------------------------------------------------
# Metric formatting helpers
# ---------------------------------------------------------------------------

def _fmt_pct(v: float, decimals: int = 2) -> str:
    if v != v or math.isinf(v):
        return "N/A"
    return f"{v * 100:.{decimals}f}%"


def _fmt_num(v: float, decimals: int = 4) -> str:
    if v != v or math.isinf(v):
        return "N/A"
    return f"{v:.{decimals}f}"


def _fmt_int(v: float) -> str:
    if v != v:
        return "N/A"
    return f"{int(v)}"


# ---------------------------------------------------------------------------
# Chart data builders
# ---------------------------------------------------------------------------

def _build_nav_chart_data(nav: pd.Series) -> Dict[str, Any]:
    """Convert NAV series to ECharts-compatible data."""
    dates = [d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d) for d in nav.index]
    values = [round(float(v), 6) for v in nav.values]
    return {"dates": dates, "values": values}


def _build_drawdown_data(nav: pd.Series) -> Dict[str, Any]:
    """Compute drawdown series for charting."""
    cummax = nav.cummax()
    dd = (nav - cummax) / cummax
    dates = [d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d) for d in dd.index]
    values = [round(float(v), 6) for v in dd.values]
    return {"dates": dates, "values": values}


def _build_monthly_returns(nav: pd.Series) -> List[Dict[str, Any]]:
    """Compute monthly return matrix."""
    if len(nav) < 2:
        return []
    rets = nav.pct_change().dropna()
    if rets.empty:
        return []
    if not hasattr(rets.index, 'to_period'):
        return []
    monthly = rets.groupby(rets.index.to_period("M")).apply(
        lambda x: float((1 + x).prod() - 1)
    )
    result = []
    for period, ret in monthly.items():
        result.append({
            "year": period.year,
            "month": period.month,
            "return": round(ret, 6),
        })
    return result


def _build_benchmark_chart_data(
    nav: pd.Series, bench: Optional[pd.Series]
) -> Optional[Dict[str, Any]]:
    """Build combined NAV + benchmark chart data."""
    if bench is None:
        return None
    nav_clean = nav.copy()
    bench_clean = bench.copy()
    if hasattr(nav_clean.index, "tz") and nav_clean.index.tz is not None:
        nav_clean.index = nav_clean.index.tz_localize(None)
    if hasattr(bench_clean.index, "tz") and bench_clean.index.tz is not None:
        bench_clean.index = bench_clean.index.tz_localize(None)
    combined = pd.concat(
        [nav_clean.to_frame("strategy"), bench_clean.to_frame("benchmark")],
        axis=1,
    ).dropna()
    if combined.empty:
        return None
    dates = [d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d) for d in combined.index]
    return {
        "dates": dates,
        "strategy": [round(float(v), 6) for v in combined["strategy"].values],
        "benchmark": [round(float(v), 6) for v in combined["benchmark"].values],
    }


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="{{ locale }}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{ title }}</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>
:root {
  --bg: {{ '#1a1a2e' if theme == 'dark' else '#ffffff' }};
  --bg2: {{ '#16213e' if theme == 'dark' else '#f8f9fa' }};
  --fg: {{ '#e0e0e0' if theme == 'dark' else '#333333' }};
  --fg2: {{ '#a0a0a0' if theme == 'dark' else '#666666' }};
  --accent: #3b82f6;
  --green: #22c55e;
  --red: #ef4444;
  --border: {{ '#2a2a4a' if theme == 'dark' else '#dee2e6' }};
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: var(--bg); color: var(--fg); font-family: -apple-system, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif; }
.container { max-width: 1200px; margin: 0 auto; padding: 20px; }
h1 { font-size: 24px; margin-bottom: 6px; }
.subtitle { color: var(--fg2); font-size: 13px; margin-bottom: 24px; }
.card { background: var(--bg2); border: 1px solid var(--border); border-radius: 10px; padding: 20px; margin-bottom: 20px; }
.card h2 { font-size: 16px; margin-bottom: 14px; color: var(--accent); }
.metrics-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; }
.metric-box { background: var(--bg); border: 1px solid var(--border); border-radius: 8px; padding: 12px; text-align: center; }
.metric-box .label { font-size: 11px; color: var(--fg2); text-transform: uppercase; letter-spacing: 0.5px; }
.metric-box .value { font-size: 20px; font-weight: 700; margin-top: 4px; }
.metric-box .value.positive { color: var(--green); }
.metric-box .value.negative { color: var(--red); }
.chart-box { width: 100%; height: 400px; }
.chart-box-sm { width: 100%; height: 300px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { padding: 8px 12px; border-bottom: 1px solid var(--border); text-align: right; }
th { color: var(--fg2); font-weight: 600; text-transform: uppercase; font-size: 11px; letter-spacing: 0.5px; }
td:first-child, th:first-child { text-align: left; }
.heatmap-cell { display: inline-block; width: 100%; text-align: center; border-radius: 4px; padding: 3px; font-size: 11px; }
.footer { text-align: center; color: var(--fg2); font-size: 12px; padding: 20px 0; }
@media (max-width: 768px) { .metrics-grid { grid-template-columns: repeat(2, 1fr); } }
</style>
</head>
<body>
<div class="container">
  <h1>{{ title }}</h1>
  <div class="subtitle">{{ strategy_name }} | {{ symbol_text }} | {{ date_range }} | Generated {{ generated_at }}</div>

  <!-- KPI Overview -->
  <div class="card">
    <h2>Performance Overview</h2>
    <div class="metrics-grid">
      {% for m in kpi_metrics %}
      <div class="metric-box">
        <div class="label">{{ m.label }}</div>
        <div class="value {{ m.css_class }}">{{ m.display }}</div>
      </div>
      {% endfor %}
    </div>
  </div>

  <!-- NAV Chart -->
  <div class="card">
    <h2>Net Asset Value</h2>
    <div id="nav-chart" class="chart-box"></div>
  </div>

  {% if drawdown_data %}
  <div class="card">
    <h2>Drawdown</h2>
    <div id="dd-chart" class="chart-box-sm"></div>
  </div>
  {% endif %}

  {% if monthly_returns %}
  <div class="card">
    <h2>Monthly Returns</h2>
    <div id="monthly-chart" class="chart-box"></div>
  </div>
  {% endif %}

  {% if risk_metrics %}
  <div class="card">
    <h2>Risk Metrics</h2>
    <div class="metrics-grid">
      {% for m in risk_metrics %}
      <div class="metric-box">
        <div class="label">{{ m.label }}</div>
        <div class="value">{{ m.display }}</div>
      </div>
      {% endfor %}
    </div>
  </div>
  {% endif %}

  {% for section in extra_sections %}
  <div class="card">
    <h2>{{ section.title }}</h2>
    {{ section.html }}
  </div>
  {% endfor %}

  <div class="footer">Generated by Unified Quant Platform V5.0 | {{ generated_at }}</div>
</div>

<script>
var THEME = "{{ theme }}";
var echTheme = THEME === "dark" ? "dark" : undefined;

// --- NAV Chart ---
(function() {
  var navData = {{ nav_chart_json }};
  var benchData = {{ bench_chart_json }};
  var el = document.getElementById("nav-chart");
  if (!el) return;
  var chart = echarts.init(el, echTheme);
  var series = [{
    name: "Strategy NAV",
    type: "line",
    data: navData.values,
    showSymbol: false,
    lineStyle: { width: 2 },
    itemStyle: { color: "#3b82f6" },
    areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
      { offset: 0, color: "rgba(59,130,246,0.3)" },
      { offset: 1, color: "rgba(59,130,246,0.02)" }
    ])}
  }];
  if (benchData) {
    series.push({
      name: "Benchmark",
      type: "line",
      data: benchData.benchmark,
      showSymbol: false,
      lineStyle: { width: 2, type: "dashed" },
      itemStyle: { color: "#f59e0b" }
    });
  }
  chart.setOption({
    tooltip: { trigger: "axis" },
    legend: { data: series.map(function(s) { return s.name; }), top: 0, textStyle: { color: THEME === "dark" ? "#ccc" : "#333" } },
    grid: { left: "6%", right: "4%", top: "14%", bottom: "16%" },
    xAxis: { type: "category", data: navData.dates, axisLabel: { rotate: 30 } },
    yAxis: { type: "value", scale: true },
    dataZoom: [
      { type: "inside", start: 0, end: 100 },
      { type: "slider", start: 0, end: 100 }
    ],
    series: series
  });
  window.addEventListener("resize", function() { chart.resize(); });
})();

// --- Drawdown Chart ---
{% if drawdown_data %}
(function() {
  var ddData = {{ drawdown_json }};
  var el = document.getElementById("dd-chart");
  if (!el) return;
  var chart = echarts.init(el, echTheme);
  chart.setOption({
    tooltip: { trigger: "axis", formatter: function(p) { return p[0].axisValue + "<br/>Drawdown: " + (p[0].value * 100).toFixed(2) + "%"; } },
    grid: { left: "6%", right: "4%", top: "10%", bottom: "16%" },
    xAxis: { type: "category", data: ddData.dates, axisLabel: { rotate: 30 } },
    yAxis: { type: "value", axisLabel: { formatter: function(v) { return (v * 100).toFixed(1) + "%"; } } },
    dataZoom: [{ type: "inside" }, { type: "slider" }],
    series: [{
      type: "line",
      data: ddData.values,
      showSymbol: false,
      lineStyle: { width: 1.5, color: "#ef4444" },
      areaStyle: { color: "rgba(239,68,68,0.2)" }
    }]
  });
  window.addEventListener("resize", function() { chart.resize(); });
})();
{% endif %}

// --- Monthly Returns Heatmap ---
{% if monthly_returns %}
(function() {
  var raw = {{ monthly_json }};
  if (!raw.length) return;
  var el = document.getElementById("monthly-chart");
  if (!el) return;
  var years = []; var monthSet = {};
  raw.forEach(function(r) {
    if (years.indexOf(r.year) === -1) years.push(r.year);
    monthSet[r.month] = true;
  });
  years.sort();
  var months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  var data = [];
  var min = 0, max = 0;
  raw.forEach(function(r) {
    var x = r.month - 1;
    var y = years.indexOf(r.year);
    data.push([x, y, r.return]);
    if (r.return < min) min = r.return;
    if (r.return > max) max = r.return;
  });
  var chart = echarts.init(el, echTheme);
  chart.setOption({
    tooltip: { formatter: function(p) { return years[p.data[1]] + " " + months[p.data[0]] + ": " + (p.data[2] * 100).toFixed(2) + "%"; } },
    grid: { left: "8%", right: "14%", top: "6%", bottom: "10%" },
    xAxis: { type: "category", data: months, splitArea: { show: true } },
    yAxis: { type: "category", data: years.map(String), splitArea: { show: true } },
    visualMap: {
      min: min, max: max, calculable: true, orient: "vertical", right: 0, top: "center",
      inRange: { color: ["#ef4444", "#fbbf24", "#22c55e"] },
      textStyle: { color: THEME === "dark" ? "#ccc" : "#333" }
    },
    series: [{
      type: "heatmap", data: data,
      label: { show: true, formatter: function(p) { return (p.data[2] * 100).toFixed(1) + "%"; }, fontSize: 10 }
    }]
  });
  window.addEventListener("resize", function() { chart.resize(); });
})();
{% endif %}
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Report generator class
# ---------------------------------------------------------------------------

class InteractiveReportGenerator:
    """Generates self-contained interactive HTML reports from backtest results."""

    def __init__(self, config: Optional[ReportConfig] = None) -> None:
        self.config = config or ReportConfig()

    def _extract_kpi(self, metrics: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extract key performance indicators for the dashboard."""
        kpis: List[Dict[str, str]] = []

        def _add(label: str, key: str, fmt: str = "pct", invert: bool = False) -> None:
            val = metrics.get(key)
            if val is None:
                return
            fval = float(val)
            if fmt == "pct":
                display = _fmt_pct(fval)
            elif fmt == "num":
                display = _fmt_num(fval)
            elif fmt == "int":
                display = _fmt_int(fval)
            else:
                display = str(fval)
            if fval != fval or math.isinf(fval):
                css = ""
            elif invert:
                css = "negative" if fval > 0 else "positive"
            else:
                css = "positive" if fval > 0 else ("negative" if fval < 0 else "")
            kpis.append({"label": label, "display": display, "css_class": css})

        _add("Total Return", "cum_return", "pct")
        _add("Annual Return", "ann_return", "pct")
        _add("Annual Volatility", "ann_vol", "pct")
        _add("Sharpe Ratio", "sharpe", "num")
        _add("Max Drawdown", "mdd", "pct", invert=True)
        _add("Calmar Ratio", "calmar", "num")
        _add("Win Rate", "win_rate", "pct")
        _add("Trades", "trades", "int")
        _add("Profit Factor", "profit_factor", "num")
        _add("Expectancy", "expectancy", "num")
        return kpis

    def _extract_risk(self, metrics: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extract risk metrics."""
        risk: List[Dict[str, str]] = []

        def _add(label: str, key: str, fmt: str = "pct") -> None:
            val = metrics.get(key)
            if val is None:
                return
            fval = float(val)
            if fmt == "pct":
                display = _fmt_pct(fval)
            else:
                display = _fmt_num(fval)
            risk.append({"label": label, "display": display, "css_class": ""})

        _add("VaR 95%", "var_95", "pct")
        _add("VaR 99%", "var_99", "pct")
        _add("CVaR 95%", "cvar_95", "pct")
        _add("CVaR 99%", "cvar_99", "pct")
        _add("Beta", "beta", "num")
        _add("Alpha (Annual)", "alpha_annual", "pct")
        _add("R-squared", "r2", "num")
        _add("Tracking Error", "tracking_error", "pct")
        _add("Information Ratio", "info_ratio", "num")
        _add("Market Correlation", "market_corr", "num")
        _add("Excess Return", "excess_return", "pct")
        _add("Benchmark Return", "bench_return", "pct")
        _add("Benchmark MDD", "bench_mdd", "pct")
        return risk

    def generate(
        self,
        metrics: Dict[str, Any],
        nav: Optional[pd.Series] = None,
        benchmark_nav: Optional[pd.Series] = None,
        extra_sections: Optional[List[ReportSection]] = None,
    ) -> str:
        """Generate a self-contained HTML report string.

        Args:
            metrics: Backtest result metrics dict (from BacktestEngine.run_strategy).
            nav: NAV series. If None, attempts to extract from metrics["nav"].
            benchmark_nav: Optional benchmark NAV series.
            extra_sections: Additional HTML sections to include.

        Returns:
            Complete HTML string.
        """
        from jinja2 import Template

        if nav is None:
            nav = metrics.get("nav")
        if nav is None or (hasattr(nav, "__len__") and len(nav) == 0):
            return "<html><body><p>No NAV data available for report.</p></body></html>"

        # Build chart data
        nav_chart = _build_nav_chart_data(nav)
        dd_data = _build_drawdown_data(nav) if self.config.include_drawdown else None
        monthly = _build_monthly_returns(nav) if self.config.include_monthly else []
        bench_chart = _build_benchmark_chart_data(nav, benchmark_nav)

        # Strategy / date info
        strategy_name = metrics.get("strategy", "Unknown Strategy")
        date_range = ""
        if len(nav) >= 2:
            first = nav.index[0]
            last = nav.index[-1]
            f_str = first.strftime("%Y-%m-%d") if hasattr(first, "strftime") else str(first)
            l_str = last.strftime("%Y-%m-%d") if hasattr(last, "strftime") else str(last)
            date_range = f"{f_str} ~ {l_str}"

        # KPI & risk
        kpi = self._extract_kpi(metrics)
        risk = self._extract_risk(metrics) if self.config.include_risk else []

        # Render
        tpl = Template(_HTML_TEMPLATE)
        html = tpl.render(
            title=self.config.title,
            theme=self.config.theme,
            locale=self.config.locale,
            strategy_name=strategy_name,
            symbol_text=str(metrics.get("symbols", "")),
            date_range=date_range,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            kpi_metrics=kpi,
            risk_metrics=risk,
            nav_chart_json=json.dumps(nav_chart),
            bench_chart_json=json.dumps(bench_chart) if bench_chart else "null",
            drawdown_data=dd_data is not None,
            drawdown_json=json.dumps(dd_data) if dd_data else "null",
            monthly_returns=bool(monthly),
            monthly_json=json.dumps(monthly),
            extra_sections=extra_sections or [],
        )
        return html

    def save(
        self,
        metrics: Dict[str, Any],
        path: str,
        nav: Optional[pd.Series] = None,
        benchmark_nav: Optional[pd.Series] = None,
        extra_sections: Optional[List[ReportSection]] = None,
    ) -> str:
        """Generate and save an HTML report to disk.

        Returns:
            Absolute path of the saved file.
        """
        html = self.generate(
            metrics, nav=nav, benchmark_nav=benchmark_nav,
            extra_sections=extra_sections,
        )
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        logger.info("report_saved", path=path, size=len(html))
        return os.path.abspath(path)

    def generate_grid_report(
        self,
        grid_df: pd.DataFrame,
        title: str = "Grid Search Report",
    ) -> str:
        """Generate an HTML report for grid search / optimization results.

        Args:
            grid_df: DataFrame from BacktestEngine.grid_search().
            title: Report title.

        Returns:
            Complete HTML string.
        """
        from jinja2 import Template

        if grid_df.empty:
            return "<html><body><p>No grid search results.</p></body></html>"

        # Build sortable table
        cols = [c for c in grid_df.columns if c not in ("nav", "_cerebro", "_quality_report")]
        rows_html = []
        for _, row in grid_df.iterrows():
            cells = []
            for c in cols:
                v = row.get(c)
                if isinstance(v, float):
                    if c in ("cum_return", "ann_return", "ann_vol", "mdd", "win_rate"):
                        cells.append(_fmt_pct(v))
                    else:
                        cells.append(_fmt_num(v))
                else:
                    cells.append(str(v) if v is not None else "")
            rows_html.append(cells)

        grid_tpl = Template(r"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>{{ title }}</title>
<style>
body { background: #1a1a2e; color: #e0e0e0; font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif; padding: 20px; }
h1 { font-size: 22px; margin-bottom: 16px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { background: #16213e; color: #3b82f6; padding: 10px; text-align: right; cursor: pointer; position: sticky; top: 0; }
th:first-child { text-align: left; }
td { padding: 8px 10px; border-bottom: 1px solid #2a2a4a; text-align: right; }
td:first-child { text-align: left; }
tr:hover { background: rgba(59,130,246,0.1); }
.footer { text-align: center; color: #666; font-size: 12px; margin-top: 20px; }
</style></head><body>
<h1>{{ title }}</h1>
<p style="color: #888; font-size: 13px;">{{ row_count }} configurations evaluated</p>
<table>
<thead><tr>{% for c in cols %}<th>{{ c }}</th>{% endfor %}</tr></thead>
<tbody>
{% for row in rows %}
<tr>{% for cell in row %}<td>{{ cell }}</td>{% endfor %}</tr>
{% endfor %}
</tbody></table>
<div class="footer">Generated by Unified Quant Platform V5.0</div>
</body></html>""")
        return grid_tpl.render(title=title, cols=cols, rows=rows_html, row_count=len(grid_df))

    def save_grid_report(self, grid_df: pd.DataFrame, path: str, title: str = "Grid Search Report") -> str:
        """Save grid search report to disk."""
        html = self.generate_grid_report(grid_df, title=title)
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        logger.info("grid_report_saved", path=path)
        return os.path.abspath(path)
