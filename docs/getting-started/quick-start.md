# Quick Start

## Run the one-click demo

```bash
python examples/one_click_demo.py --out-dir report/open_source_demo
```

This command generates a deterministic paper-trading report, a Markdown summary, and ECharts-ready JSON from bundled sample data. It does not require broker SDKs, provider tokens, or network data access.

## Run a backtest

```bash
python unified_backtest_framework.py run \
  --strategy macd \
  --symbols 600519.SH \
  --start 2023-01-01 --end 2024-12-31 \
  --plot
```

## Open the classic GUI

```bash
python scripts/backtest_gui.py
```

## Run the platform API and web console with Docker Compose

```bash
docker compose up
```

Then open `http://localhost:3000` for the web console and `http://localhost:8000/api/v2/docs` for the OpenAPI UI.

## Run a deterministic paper-trading demo

```bash
python scripts/demo_platform_console.py --out report/platform_console_demo.json
```

This path uses the built-in paper gateway and does not require a broker SDK.

## Next steps

- [Backtesting guide](../guides/backtesting.md)
- [Strategy admission guide](../guides/strategy-admission.md)
- [Web console guide](../guides/web-console.md)