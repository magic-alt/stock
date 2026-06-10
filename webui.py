"""Start the local WebUI.

Usage:
    python webui.py
    WEBUI_HOST=0.0.0.0 WEBUI_PORT=8001 python webui.py

The implementation lives in scripts/run_web_console.py so the documented
script entry point and this daily_stock_analysis-style shortcut stay aligned.
"""
from __future__ import annotations

from scripts.run_web_console import main


if __name__ == "__main__":
    raise SystemExit(main())
