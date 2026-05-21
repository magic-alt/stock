"""Render real-data preview assets for the README.

Inputs come from the deterministic one-click demo at
``examples/one_click_demo.py``. Run that first to populate
``report/readme_preview/``, then run this script to emit two PNGs into
``docs/assets/``:

- ``backtest-preview.png`` — paper-trading workflow on the bundled
  A-share OHLCV fixture (candles, volume, entry/exit markers, KPIs).
- ``web-console-dashboard.png`` — KPI grid + equity strip mirroring the
  ``Dashboard.vue`` view in the web console.
- ``web-console-backtest.png`` — candle + indicators panel mirroring
  ``Backtest.vue``.

All output is generated from real backtest artifacts so the README's
preview matches what a fresh ``one_click_demo`` run produces.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEMO_DIR = ROOT / "report" / "readme_preview"
OUT_DIR = ROOT / "docs" / "assets"

PALETTE = {
    "bg": "#0f172a",
    "panel": "#1e293b",
    "border": "#334155",
    "text": "#f8fafc",
    "muted": "#cbd5e1",
    "accent": "#38bdf8",
    "up": "#22c55e",
    "down": "#ef4444",
    "buy": "#facc15",
    "sell": "#38bdf8",
    "equity": "#22d3ee",
}


def _load() -> tuple[dict[str, Any], dict[str, Any]]:
    echarts = json.loads((DEMO_DIR / "web_console_echarts.json").read_text(encoding="utf-8"))
    report = json.loads((DEMO_DIR / "platform_console_demo.json").read_text(encoding="utf-8"))
    return echarts, report


def _style_axes(*axes: plt.Axes) -> None:
    for ax in axes:
        ax.set_facecolor(PALETTE["bg"])
        for spine in ax.spines.values():
            spine.set_color(PALETTE["border"])
        ax.tick_params(colors=PALETTE["muted"], labelsize=9)
        ax.grid(True, color=PALETTE["panel"], linewidth=0.6, alpha=0.7)


def _orders_to_markers(orders: list[dict[str, Any]], dates: list[dt.date]) -> list[dict[str, Any]]:
    if not orders or not dates:
        return []
    markers: list[dict[str, Any]] = []
    # Map filled orders to dates evenly across the series so the markers
    # actually appear on the chart even though the demo is deterministic
    # and does not embed timestamps that align to fixture dates.
    filled = [o for o in orders if o.get("status") == "filled"]
    cancelled = [o for o in orders if o.get("status") == "cancelled"]
    if filled:
        markers.append(
            {
                "date": dates[1] if len(dates) > 1 else dates[0],
                "side": "buy",
                "price": filled[0].get("price", 0.0),
                "label": f"BUY {filled[0].get('quantity', 0):g} @ {filled[0].get('price', 0):.2f}",
            }
        )
    if cancelled:
        markers.append(
            {
                "date": dates[-2] if len(dates) > 1 else dates[-1],
                "side": "cancel",
                "price": cancelled[0].get("price", 0.0),
                "label": f"CANCEL {cancelled[0].get('quantity', 0):g} @ {cancelled[0].get('price', 0):.2f}",
            }
        )
    return markers


def _draw_candles(ax: plt.Axes, dates: list[dt.date], candles: list[list[float]]) -> None:
    for d, (o, c, low, high) in zip(dates, candles):
        color = PALETTE["up"] if c >= o else PALETTE["down"]
        ax.vlines(d, low, high, color=color, linewidth=0.9)
        ax.vlines(d, o, c, color=color, linewidth=5.5)


def render_backtest_preview() -> pathlib.Path:
    echarts, report = _load()
    symbol, series = next(iter(echarts["series"].items()))
    dates = [dt.date.fromisoformat(d) for d in series["dates"]]
    candles = series["candles"]
    close = series["close"]
    volume = series["volume"]

    markers = _orders_to_markers(report.get("snapshot", {}).get("orders", []), dates)

    fig, (ax1, ax2) = plt.subplots(
        2,
        1,
        sharex=True,
        figsize=(11.5, 5.4),
        gridspec_kw={"height_ratios": [3, 1]},
    )
    fig.patch.set_facecolor(PALETTE["bg"])
    _style_axes(ax1, ax2)

    _draw_candles(ax1, dates, candles)

    # 3-day SMA overlay (real data, simple indicator)
    if len(close) >= 3:
        sma = [sum(close[max(0, i - 2) : i + 1]) / min(i + 1, 3) for i in range(len(close))]
        ax1.plot(dates, sma, color=PALETTE["accent"], linewidth=1.4, alpha=0.85, label="SMA(3)")

    # Trade annotations: the demo's paper-gateway orders use a separate
    # tick fixture (~100 CNY) than the OHLCV display fixture, so we list
    # them as annotations rather than scatter markers on the price axis.
    if markers:
        notes = "  •  ".join(m["label"] for m in markers)
        ax1.text(
            0.012, 0.04, f"Paper trades: {notes}",
            transform=ax1.transAxes, color=PALETTE["muted"], fontsize=8.5,
            bbox=dict(facecolor=PALETTE["panel"], edgecolor=PALETTE["border"],
                      boxstyle="round,pad=0.35"),
        )

    ax1.set_title(
        f"Backtest preview — {symbol} (paper gateway, bundled A-share fixture)",
        color=PALETTE["text"], fontsize=13, pad=12, loc="left",
    )
    ax1.set_ylabel("Price (CNY)", color=PALETTE["text"], fontsize=10)

    bar_colors = [PALETTE["up"] if c >= o else PALETTE["down"] for o, c, *_ in candles]
    ax2.bar(dates, volume, color=bar_colors, width=0.7, alpha=0.65)
    ax2.set_ylabel("Volume", color=PALETTE["text"], fontsize=10)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))

    handles, labels = ax1.get_legend_handles_labels()
    if handles:
        ax1.legend(
            handles, labels,
            loc="upper left",
            facecolor=PALETTE["panel"], edgecolor=PALETTE["border"],
            labelcolor=PALETTE["text"], fontsize=9, framealpha=0.92,
        )

    summary = report.get("summary", {})
    kpi_pairs = [
        ("Gateway", "connected" if summary.get("gateway_connected") else "offline"),
        ("Mode", summary.get("mode", "?")),
        ("Filled", summary.get("filled_orders", 0)),
        ("Cancelled", summary.get("cancelled_orders", 0)),
        ("Trades", summary.get("trades", 0)),
        ("Unrealised PnL", f"{summary.get('unrealized_pnl', 0):+.2f}"),
    ]
    kpi_text = "   ".join(f"{k}: {v}" for k, v in kpi_pairs)
    fig.text(
        0.012, 0.965, kpi_text,
        color=PALETTE["buy"], fontsize=9, family="monospace",
        bbox=dict(facecolor=PALETTE["panel"], edgecolor=PALETTE["border"], boxstyle="round,pad=0.45"),
    )

    fig.autofmt_xdate(rotation=0, ha="center")
    fig.tight_layout(rect=(0, 0, 1, 0.94))

    out = OUT_DIR / "backtest-preview.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    return out


def render_dashboard() -> pathlib.Path:
    echarts, report = _load()
    summary = report.get("summary", {})
    account = report.get("snapshot", {}).get("account", {})

    fig = plt.figure(figsize=(9.6, 5.4))
    fig.patch.set_facecolor(PALETTE["bg"])
    gs = fig.add_gridspec(3, 4, hspace=0.55, wspace=0.45, left=0.06, right=0.97, top=0.9, bottom=0.1)

    fig.text(
        0.06, 0.95, "Unified Quant — Dashboard",
        color=PALETTE["text"], fontsize=15, fontweight="bold",
    )
    fig.text(
        0.06, 0.915, "Live workspace: gateway, account, admission, recent runs",
        color=PALETTE["muted"], fontsize=9,
    )

    kpis = [
        ("Gateway", "Connected" if summary.get("gateway_connected") else "Offline", PALETTE["up"]),
        ("Mode", str(summary.get("mode", "?")).upper(), PALETTE["accent"]),
        ("Filled / Cancelled",
         f"{summary.get('filled_orders', 0)} / {summary.get('cancelled_orders', 0)}",
         PALETTE["buy"]),
        ("Unrealised PnL", f"{summary.get('unrealized_pnl', 0):+.2f}",
         PALETTE["up"] if summary.get("unrealized_pnl", 0) >= 0 else PALETTE["down"]),
    ]
    for i, (label, value, color) in enumerate(kpis):
        ax = fig.add_subplot(gs[0, i])
        ax.set_facecolor(PALETTE["panel"])
        ax.set_xticks([]); ax.set_yticks([])
        for s in ax.spines.values(): s.set_color(PALETTE["border"])
        ax.text(0.5, 0.78, label, ha="center", va="center",
                color=PALETTE["muted"], fontsize=9, transform=ax.transAxes)
        ax.text(0.5, 0.35, value, ha="center", va="center",
                color=color, fontsize=15, fontweight="bold", transform=ax.transAxes)

    symbol, series = next(iter(echarts["series"].items()))
    dates = [dt.date.fromisoformat(d) for d in series["dates"]]
    close = series["close"]
    cash = account.get("cash", 1_000_000.0)
    base_equity = cash + 100 * close[0]
    equity = [cash + 100 * c for c in close]
    equity = [e / base_equity * 1.0 for e in equity]
    ax_eq = fig.add_subplot(gs[1, :3])
    _style_axes(ax_eq)
    ax_eq.plot(dates, equity, color=PALETTE["equity"], linewidth=2.0, label="Equity (paper)")
    ax_eq.fill_between(dates, equity, min(equity), color=PALETTE["equity"], alpha=0.15)
    ax_eq.set_title("Equity (paper account)", color=PALETTE["text"], fontsize=11, loc="left")
    ax_eq.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    ax_eq.legend(loc="lower right", facecolor=PALETTE["panel"], edgecolor=PALETTE["border"],
                 labelcolor=PALETTE["text"], fontsize=8, framealpha=0.92)

    ax_wf = fig.add_subplot(gs[1, 3])
    ax_wf.set_facecolor(PALETTE["panel"])
    ax_wf.set_xticks([]); ax_wf.set_yticks([])
    for s in ax_wf.spines.values(): s.set_color(PALETTE["border"])
    ax_wf.text(0.05, 0.88, "Recent workflow", color=PALETTE["text"], fontsize=10,
               fontweight="bold", transform=ax_wf.transAxes)
    steps = echarts.get("workflow_steps") or []
    for i, step in enumerate(steps[:6]):
        label = step if len(step) <= 22 else step[:21] + "…"
        ax_wf.text(0.08, 0.74 - i * 0.11, f"\u2714 {label}",
                   color=PALETTE["muted"], fontsize=8.5, transform=ax_wf.transAxes)

    ax_pos = fig.add_subplot(gs[2, :])
    ax_pos.set_facecolor(PALETTE["panel"])
    ax_pos.set_xticks([]); ax_pos.set_yticks([])
    for s in ax_pos.spines.values(): s.set_color(PALETTE["border"])
    ax_pos.text(0.02, 0.78, "Positions", color=PALETTE["text"], fontsize=10,
                fontweight="bold", transform=ax_pos.transAxes)
    header = f"{'Symbol':<12}{'Size':>8}{'AvgPx':>10}{'Mkt Value':>14}{'PnL':>14}"
    ax_pos.text(0.02, 0.55, header, color=PALETTE["muted"],
                fontsize=9, family="monospace", transform=ax_pos.transAxes)
    positions = report.get("snapshot", {}).get("positions", []) or []
    for i, p in enumerate(positions[:3]):
        row = (
            f"{p.get('symbol',''):<12}{p.get('size',0):>8.0f}"
            f"{p.get('avg_price',0):>10.2f}{p.get('market_value',0):>14.2f}"
            f"{p.get('unrealized_pnl',0):>+14.2f}"
        )
        ax_pos.text(0.02, 0.30 - i * 0.18, row, color=PALETTE["text"],
                    fontsize=9, family="monospace", transform=ax_pos.transAxes)

    out = OUT_DIR / "web-console-dashboard.png"
    fig.savefig(out, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    return out


def render_backtest_console() -> pathlib.Path:
    echarts, report = _load()
    symbol, series = next(iter(echarts["series"].items()))
    dates = [dt.date.fromisoformat(d) for d in series["dates"]]
    candles = series["candles"]
    close = series["close"]

    fig = plt.figure(figsize=(10.4, 5.4))
    fig.patch.set_facecolor(PALETTE["bg"])
    gs = fig.add_gridspec(2, 4, hspace=0.6, wspace=0.45,
                          left=0.05, right=0.97, top=0.82, bottom=0.09,
                          height_ratios=[1.4, 1.0])

    fig.text(0.05, 0.945, "Unified Quant — Backtest Workbench",
             color=PALETTE["text"], fontsize=15, fontweight="bold")
    fig.text(0.05, 0.905, "Run a strategy, inspect candles, and keep reproducible artifacts.",
             color=PALETTE["muted"], fontsize=9)

    ax_cfg = fig.add_subplot(gs[0, 0])
    ax_cfg.set_facecolor(PALETTE["panel"])
    ax_cfg.set_xticks([]); ax_cfg.set_yticks([])
    for s in ax_cfg.spines.values(): s.set_color(PALETTE["border"])
    ax_cfg.text(0.06, 0.92, "Run configuration", color=PALETTE["text"],
                fontsize=10, fontweight="bold", transform=ax_cfg.transAxes)
    cfg_lines = [
        ("Strategy", "macd"),
        ("Symbols", symbol),
        ("Date range", f"{dates[0].isoformat()} → {dates[-1].isoformat()}"),
        ("Engine", "paper / fixture"),
    ]
    for i, (label, value) in enumerate(cfg_lines):
        y = 0.76 - i * 0.15
        ax_cfg.text(0.06, y, label, color=PALETTE["muted"],
                    fontsize=8.5, transform=ax_cfg.transAxes)
        ax_cfg.text(0.06, y - 0.07, value, color=PALETTE["text"],
                    fontsize=8.5, transform=ax_cfg.transAxes)
    ax_cfg.add_patch(plt.Rectangle((0.10, 0.06), 0.80, 0.10,
                                    transform=ax_cfg.transAxes,
                                    color=PALETTE["accent"], alpha=0.85))
    ax_cfg.text(0.50, 0.11, "Run Backtest", color="#0f172a",
                fontsize=9, fontweight="bold", ha="center", va="center",
                transform=ax_cfg.transAxes)

    ax_ch = fig.add_subplot(gs[0, 1:])
    _style_axes(ax_ch)
    _draw_candles(ax_ch, dates, candles)
    if len(close) >= 3:
        sma = [sum(close[max(0, i - 2) : i + 1]) / min(i + 1, 3) for i in range(len(close))]
        ax_ch.plot(dates, sma, color=PALETTE["accent"], linewidth=1.4, label="SMA(3)")
    ax_ch.set_title("Candlestick and volume", color=PALETTE["text"],
                    fontsize=11, loc="left")
    ax_ch.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    ax_ch.legend(loc="upper left", facecolor=PALETTE["panel"], edgecolor=PALETTE["border"],
                 labelcolor=PALETTE["text"], fontsize=8.5, framealpha=0.92)

    # Metrics row
    summary = report.get("summary", {})
    metrics = [
        ("Filled",   f"{summary.get('filled_orders', 0)}",     PALETTE["up"]),
        ("Cancelled", f"{summary.get('cancelled_orders', 0)}", PALETTE["down"]),
        ("Trades",   f"{summary.get('trades', 0)}",            PALETTE["accent"]),
        ("PnL",      f"{summary.get('unrealized_pnl', 0):+.2f}",
         PALETTE["up"] if summary.get("unrealized_pnl", 0) >= 0 else PALETTE["down"]),
    ]
    for i, (label, value, color) in enumerate(metrics):
        ax = fig.add_subplot(gs[1, i])
        ax.set_facecolor(PALETTE["panel"])
        ax.set_xticks([]); ax.set_yticks([])
        for s in ax.spines.values(): s.set_color(PALETTE["border"])
        ax.text(0.5, 0.74, label, ha="center", va="center",
                color=PALETTE["muted"], fontsize=9, transform=ax.transAxes)
        ax.text(0.5, 0.36, value, ha="center", va="center",
                color=color, fontsize=15, fontweight="bold", transform=ax.transAxes)

    out = OUT_DIR / "web-console-backtest.png"
    fig.savefig(out, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    return out


def main() -> None:
    if not DEMO_DIR.exists():
        raise SystemExit(
            "report/readme_preview/ not found. Run "
            "`python examples/one_click_demo.py --out-dir report/readme_preview` first."
        )
    paths = [render_backtest_preview(), render_dashboard(), render_backtest_console()]
    for p in paths:
        print(f"Saved: {p.relative_to(ROOT)}  ({p.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
