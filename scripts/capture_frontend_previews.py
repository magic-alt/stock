"""Capture real screenshots of the running Vue frontend for README previews.

Prerequisite: the Docker stack must be running (`docker compose up -d api frontend`)
so that the frontend is reachable on http://localhost:3000 and the API on
http://localhost:8000.

Usage:
    python -m playwright install chromium   # one-off
    python scripts/capture_frontend_previews.py

Outputs:
    docs/assets/web-console-dashboard.png   — Dashboard view (real frontend)
    docs/assets/web-console-backtest.png    — Backtest workbench view (real frontend)
"""
from __future__ import annotations

import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "assets"
OUT_DIR.mkdir(parents=True, exist_ok=True)

FRONTEND_URL = "http://localhost:3000"
VIEWPORT = {"width": 1440, "height": 900}


def _try_run_backtest(page) -> None:
    """Best-effort: trigger a backtest from the Backtest page so the chart panel
    becomes populated. If anything fails we still screenshot the page as-is."""
    try:
        symbol_input = page.get_by_placeholder("600519.SH,000001.SZ")
        if symbol_input.count() > 0:
            symbol_input.first.fill("600519.SH")
        run_btn = page.get_by_role("button", name="Run Backtest")
        if run_btn.count() == 0:
            run_btn = page.get_by_role("button", name="Submit Backtest Job")
        if run_btn.count() > 0:
            run_btn.first.click()
            page.wait_for_selector(".backtest-chart", timeout=120_000)
            # Wait for the ECharts canvas to actually have data.
            time.sleep(5.0)
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] backtest trigger failed (continuing with current state): {exc}")


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright not installed. Run: python -m pip install playwright && python -m playwright install chromium")
        return 1

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            context = browser.new_context(viewport=VIEWPORT, device_scale_factor=1.5)
            page = context.new_page()

            # 1) Dashboard — viewport screenshot so the framing matches the README thumbnail.
            dashboard_path = OUT_DIR / "web-console-dashboard.png"
            print(f"[capture] {FRONTEND_URL}/ -> {dashboard_path.relative_to(ROOT)}")
            page.goto(f"{FRONTEND_URL}/", wait_until="networkidle", timeout=60_000)
            time.sleep(2.5)
            page.evaluate("window.scrollTo(0, 0)")
            page.screenshot(path=str(dashboard_path), full_page=False)

            # 2) Backtest — run a real backtest, then screenshot the result card
            #    (chart + KPIs) directly so the preview is compact and meaningful.
            backtest_path = OUT_DIR / "web-console-backtest.png"
            print(f"[capture] {FRONTEND_URL}/backtest -> {backtest_path.relative_to(ROOT)}")
            page.goto(f"{FRONTEND_URL}/backtest", wait_until="networkidle", timeout=60_000)
            time.sleep(1.5)
            _try_run_backtest(page)

            # Prefer the result card (Results: <strategy> ...) so the screenshot is focused.
            chart_card = page.locator(".dark-card", has=page.locator(".backtest-chart"))
            if chart_card.count() > 0:
                chart_card.first.scroll_into_view_if_needed()
                time.sleep(1.0)
                chart_card.first.screenshot(path=str(backtest_path))
                _trim_trailing_blank(backtest_path)
            else:
                page.screenshot(path=str(backtest_path), full_page=False)
        finally:
            browser.close()

    print("[done] previews saved under docs/assets/")
    return 0


def _trim_trailing_blank(path: pathlib.Path) -> None:
    """Crop a screenshot's trailing rows of near-uniform background colour
    (the result card often extends past its visible content)."""
    try:
        from PIL import Image
    except ImportError:
        return
    with Image.open(path) as im:
        rgb = im.convert("RGB")
        w, h = rgb.size
        # Background colour sampled from the bottom-right (almost always the
        # blank card body padding beyond the last rendered child).
        bg = rgb.getpixel((w - 4, h - 4))

        def _row_is_blank(y: int) -> bool:
            sample_xs = range(0, w, max(1, w // 60))
            for x in sample_xs:
                r, g, b = rgb.getpixel((x, y))
                if abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2]) > 36:
                    return False
            return True

        last_content_row = h - 1
        while last_content_row > 0 and _row_is_blank(last_content_row):
            last_content_row -= 1
        new_h = min(h, last_content_row + 24)
        if new_h < h - 8:
            rgb.crop((0, 0, w, new_h)).save(path)
            print(f"[trim] {path.name}: {h} -> {new_h} px")


if __name__ == "__main__":
    sys.exit(main())
