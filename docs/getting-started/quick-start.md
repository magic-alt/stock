# Quick Start

## Run the one-click demo

```bash
python examples/one_click_demo.py --out-dir report/open_source_demo
```

This command generates a paper-trading report, a Markdown summary, and ECharts-ready JSON. It does not require broker SDKs.

## Open the beginner Dashboard

Start the FastAPI v2 server:

```bash
python scripts/run_platform_api.py
```

Then start the frontend:

```bash
cd frontend
npm ci
npm run dev
```

Open `http://localhost:3000`. The Dashboard analysis panel defaults to `source=auto`, which fetches real OHLCV data from web/provider sources starting with Eastmoney. AI summaries are optional and only run when enabled plus `OPENAI_API_KEY` is configured.

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
