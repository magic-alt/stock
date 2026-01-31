# Platform Guide

This project now ships a lightweight platform layer for web APIs, job orchestration, containerization, and distributed backtests. The goal is to keep dependencies minimal while enabling automation.

## 1) Web API + Job Queue

Run the API server:
```
python scripts/run_platform_api.py --host 0.0.0.0 --port 8080
```

Endpoints:
- `GET /health` -> service status
- `GET /jobs` -> list jobs
- `GET /jobs/{id}` -> job detail
- `POST /jobs/backtest` -> submit backtest job
- `POST /jobs/workflow` -> submit a multi-step workflow

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

Example workflow payload:
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

Local distributed backtest runner (process pool):
```
from src.platform.distributed import run_distributed_backtests
results = run_distributed_backtests(payloads, max_workers=4)
```

## 5) Containerization

Use the provided `Dockerfile` and `docker-compose.yml` to run the API server. Kubernetes manifests are in `deploy/k8s/`.
