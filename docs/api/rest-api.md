# REST API

The production REST surface is implemented in `src/platform/api_v2.py` and exposed under `/api/v2/*`.

## Local OpenAPI

When the API server is running, open:

```text
http://localhost:8000/api/v2/docs
```

## Key endpoint groups

- Health and readiness: `/api/v2/health`, `/api/v2/ready`
- Platform info: `/api/v2/info` exposes the API version, V6 `contract_version`, and runtime policies.
- Beginner stock analysis: `/api/v2/analysis/run`, `/api/v2/analysis/jobs`, `/api/v2/analysis/capabilities`
- Backtest execution: `/api/v2/backtest/run`, `/api/v2/backtest/jobs`
- Strategy library and validation: `/api/v2/strategies`
- Gateway operations: `/api/v2/gateway/*`
- Monitoring: `/api/v2/monitor/*`
- Demo: `/api/v2/demo/paper-trading`

See [API reference](../API_REFERENCE.md) for the detailed contract.
