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

## Main views

- Dashboard: platform status and recent backtests
- Backtest: strategy run form and result charts
- Trading: paper/live gateway console
- Strategies: strategy library and quick actions
- Data: OHLCV browser
- Monitor: system, gateway, queue, and alert snapshots

## Related references

- [Platform guide](../PLATFORM_GUIDE.md)
- [REST API](../api/rest-api.md)