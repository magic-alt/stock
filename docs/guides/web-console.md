# Web Console

The web console is a Vue3 + Vite + Element Plus application backed by the FastAPI v2 service.

## Local development

Start the WebUI with one command:

```bash
python webui.py
```

The script builds or reuses `frontend/dist`, starts FastAPI on
`127.0.0.1:8001`, serves the frontend from that same backend, and opens the
browser. Use `--no-open` to keep the browser closed. Use `--dev` when you want
the Vite development server with hot reload.

The Dashboard is the recommended first screen. Its Beginner Analysis panel runs
against real market data by default, returns a rule-based rating, reasons,
risks, a lightweight backtest preview, and a copyable Markdown report. Real
providers can be selected after local data dependencies are configured. AI
summaries are optional and require `OPENAI_API_KEY`.

## Main views

- Dashboard: beginner stock analysis, platform status, quick actions, and recent backtests
- Backtest: strategy run form and result charts
- Trading: paper/live gateway console
- Strategies: strategy library and quick actions
- Data: local DuckDB OHLCV datasets, update action, K-line chart, and table browser
- Monitor: system, gateway, queue, and alert snapshots

## Related references

- [Platform guide](../PLATFORM_GUIDE.md)
- [REST API](../api/rest-api.md)
