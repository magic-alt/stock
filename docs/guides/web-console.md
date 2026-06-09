# Web Console

The web console is a Vue3 + Vite + Element Plus application backed by the FastAPI v2 service.

## Local development

Start the API server, then run the frontend dev server:

```bash
python scripts/run_platform_api.py
```

```bash
cd frontend
npm ci
npm run dev
```

Open `http://localhost:3000`.

The Dashboard is the recommended first screen. Its Beginner Analysis panel runs
against bundled sample data by default, returns a rule-based rating, reasons,
risks, a lightweight backtest preview, and a copyable Markdown report. Real
providers can be selected after local data dependencies are configured. AI
summaries are optional and require `OPENAI_API_KEY`.

## Main views

- Dashboard: beginner stock analysis, platform status, quick actions, and recent backtests
- Backtest: strategy run form and result charts
- Trading: paper/live gateway console
- Strategies: strategy library and quick actions
- Data: OHLCV browser
- Monitor: system, gateway, queue, and alert snapshots

## Related references

- [Platform guide](../PLATFORM_GUIDE.md)
- [REST API](../api/rest-api.md)
