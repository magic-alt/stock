# Platform Guide

This project ships a platform layer for REST APIs, job orchestration, containerization, the Vue web console, and distributed backtests. The current production API entrypoint is FastAPI v2.

## 1) Web API + Job Queue

Run the API server:
```
python -m uvicorn src.platform.api_v2:app --host 0.0.0.0 --port 8000
```

Endpoints:
- `GET /api/v2/health` -> service status
- `GET /api/v2/ready` -> readiness
- `GET /api/v2/metrics` -> API and queue metrics
- `GET /api/v2/docs` -> OpenAPI/Swagger UI
- `POST /api/v2/backtest/run` -> run a synchronous backtest
- `POST /api/v2/backtest/jobs` -> submit an asynchronous backtest job
- `GET /api/v2/backtest/jobs/{id}` -> job detail
- `POST /api/v2/backtest/jobs/{id}/cancel` -> cancel a pending job
- `GET /api/v2/strategies` -> list registered strategies
- `POST /api/v2/gateway/order` -> submit an order through the platform gateway

Example backtest payload:
```
{
  "strategy": "qlib_registry",
  "symbols": ["600519.SH"],
  "start": "2017-01-03",
  "end": "2018-12-31",
  "source": "qlib",
  "params": {"model_name": "qlib-csi300", "provider_uri": "./qlib_data"},
  "plot": true
}
```

## 2) Workflow Orchestration

The job queue supports JSON/SQLite/Redis-backed persistence and idempotent submission. DAG workflow execution lives in `src/platform/orchestrator.py`; steps in the same dependency layer can run in parallel.

Example workflow step payload:
```
{
  "steps": [
    {"task_type": "backtest", "payload": {"strategy": "ema", "symbols": ["600519.SH"], "start": "2020-01-01", "end": "2020-12-31"}},
    {"task_type": "backtest", "payload": {"strategy": "macd", "symbols": ["600519.SH"], "start": "2021-01-01", "end": "2021-12-31"}}
  ]
}
```

## 3) Data Lake (Local)

Backtest reports can be registered into the local data lake (`./data_lake/manifest.json`). This provides artifact versioning for reports and datasets.

## 4) Distributed Backtests

Distributed backtest runner:
```
from src.platform.distributed import run_distributed_backtests
results = run_distributed_backtests(payloads, max_workers=4, backend="local")
```

Supported backends are `local` (ProcessPool), `ray`, and `dask`. Ray/Dask require their optional packages and cluster configuration.

## 5) Containerization

Use the provided `Dockerfile` and `docker-compose.yml` to run the API server, Vue frontend, and Redis:

```
docker compose up -d
```

Kubernetes manifests are in `deploy/k8s/`. The production API image can also serve `frontend/dist` directly when `PLATFORM_FRONTEND_DIST` points to the built frontend.

## 6) Mid/Long-Term Plan Status

The old P2/P3 checklist has been re-audited against the current code:

- P2 REST API, Docker containerization, and config encryption are implemented.
- P3 Web frontend is implemented.
- P3 distributed backtest is implemented at framework level and still needs production cluster hardening.
- P3 microservice architecture remains partial.

See [中长期规划实现状态审计](MID_LONG_TERM_STATUS_AUDIT.md).
