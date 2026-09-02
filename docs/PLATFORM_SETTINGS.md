# Platform Settings SSOT

Status: Gate 1 / PR 4 runtime configuration contract.

The platform resolves runtime configuration through `src.core.settings.PlatformSettings`. Application code should receive the resolved object (or explicit values derived from it) instead of re-reading environment variables in each subsystem.

## Precedence

The precedence contract is fixed and testable:

```text
CLI overrides
    > environment variables
    > config.yaml
    > safe defaults
```

Examples:

- `python scripts/run_platform_api.py --port 9000` beats `PLATFORM_API_PORT=8000`.
- `PLATFORM_JOB_STORE=/data/jobs.sqlite` beats `platform.job_store` in `config.yaml`.
- `config.yaml` beats model defaults when neither CLI nor environment provides the value.

`PLATFORM_CONFIG=/path/to/config.yaml` selects a YAML file. `--config` on the API startup script has higher precedence than `PLATFORM_CONFIG`.

## Canonical runtime environment variables

| Setting | Environment variable | Safe/default behavior |
| --- | --- | --- |
| API bind host | `PLATFORM_API_HOST` | `0.0.0.0` |
| API bind port | `PLATFORM_API_PORT` | `8000` |
| CORS origins | `PLATFORM_ALLOWED_ORIGINS` | localhost frontend origins |
| SPA distribution | `PLATFORM_FRONTEND_DIST` | repository `frontend/dist` when present |
| Auth disabled | `PLATFORM_API_AUTH_DISABLED` | `false` |
| Bootstrap Bearer token | `PLATFORM_API_TOKEN` | empty; readiness fails when auth is enabled |
| Bootstrap subject | `PLATFORM_API_TOKEN_SUBJECT` | `bootstrap-admin` |
| Bootstrap role | `PLATFORM_API_TOKEN_ROLE` | `admin` |
| Audit log | `PLATFORM_AUDIT_LOG` | `./logs/audit.log` |
| Job store | `PLATFORM_JOB_STORE` | `./cache/platform/jobs.json` |
| Job store fallback | `PLATFORM_JOB_STORE_FALLBACK` | local-development fallback enabled |
| Job workers | `PLATFORM_JOB_MAX_WORKERS` | `2` |
| Local market DuckDB | `MARKET_DATA_DUCKDB_PATH` | `database.duckdb_path` / safe default |
| OpenAI-compatible key | `OPENAI_API_KEY` | empty |
| OpenAI-compatible base URL | `OPENAI_BASE_URL` | model default |
| OpenAI-compatible model | `OPENAI_MODEL` | model default |

`PORT` remains accepted as a backward-compatible alias for `PLATFORM_API_PORT`, but Docker Compose and Kubernetes use `PLATFORM_API_PORT` so there is one deployment-facing name.

Historical `BACKTEST_*` variables remain compatibility aliases. They are resolved inside the same `PlatformSettings` layer; `ConfigManager` no longer owns a second environment-precedence implementation.

## Production fail-closed rules

Production should set:

```text
PLATFORM_API_AUTH_DISABLED=0
PLATFORM_API_TOKEN=<secret>
PLATFORM_JOB_STORE_FALLBACK=0
```

If authentication is enabled but the bootstrap token is empty, `config doctor` reports an error and API readiness remains false. Remote Redis/PostgreSQL JobStore configurations with fallback enabled are reported as a warning because silent local fallback breaks distributed state assumptions.

Secrets belong in environment/secret managers rather than committed YAML. The Kubernetes deployment already loads the API token from `platform-api-secrets`.

## Config doctor

Inspect the effective configuration before deployment:

```bash
quant-platform config doctor
```

Machine-readable form:

```bash
quant-platform config doctor --json
```

Use a specific YAML file:

```bash
quant-platform config doctor --config ./config.yaml
```

The command reports:

- the precedence contract;
- the selected YAML path;
- effective configuration values;
- the source (`cli`, `env:...`, `yaml`, or `default`) for resolved fields;
- cross-setting errors and warnings.

Secret values are redacted. The diagnostic output must never print `PLATFORM_API_TOKEN`, provider tokens, or AI API keys in plaintext.

## Application integration rule

Application factories should resolve once at the process boundary:

```text
startup / CLI
    -> load_platform_settings()
    -> PlatformSettings
    -> FastAPI app.state.settings
       -> JobStore
       -> API authentication/audit
       -> CORS / SPA path
       -> DuckDB path
       -> runtime services
```

Do not pass runtime configuration internally by mutating `os.environ`. Do not introduce new `os.getenv()` precedence logic inside workers, gateways, routers, or services when the setting belongs to `PlatformSettings`.

Tests may inject a pre-resolved `PlatformSettings` directly into `create_app(settings=...)`. This is the preferred replacement for changing a module-global `ConfigManager` merely to influence the API factory.

## Deployment alignment

The production surfaces use the same names:

- Dockerfile: `PLATFORM_API_HOST` / `PLATFORM_API_PORT` and `scripts/run_platform_api.py`;
- Docker Compose: canonical API, JobStore, DuckDB, audit settings;
- Kubernetes: the same names, with `PLATFORM_JOB_STORE_FALLBACK=0`;
- health/readiness remains on internal port `8000`.

Host-side Compose port publication remains separately configurable through `PLATFORM_HOST_PORT`; it does not change the API process bind port.

## Compatibility boundary

`src.core.config.GlobalConfig` remains the typed domain schema for backtest, risk, data, execution, monitoring and portfolio fields. `ConfigManager` is retained as a compatibility facade for existing callers and persistence helpers, but runtime source precedence belongs to `PlatformSettings`.

The next strict ROADMAP item after this PR is **Gate 1 / PR 5 — API contract normalization**. Router decomposition and durable live-control state remain later PRs.
