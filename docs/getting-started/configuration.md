# Configuration

Copy the environment template before first use. The Web Settings page reads and writes this same local `.env` file, so values changed in Settings persist across WebUI restarts.

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

If `.env` is missing, the FastAPI WebUI creates it from `.env.example` during startup. Use `STOCK_ENV_PATH=/path/to/.env` to point the WebUI and Settings API at a different local environment file.

## Web Settings

The Settings page groups all `GlobalConfig` options by category and saves them as `STOCK__SECTION__FIELD=value` entries in `.env`. Values use JSON-compatible literals:

- strings: `"akshare"`
- booleans: `true` / `false`
- empty optional values: `null`
- lists and objects: `[]` / `{}`

Legacy `config.yaml` loading remains supported for command-line compatibility, but the Web Settings page persists changes to `.env`.

## Data Provider Tokens

TuShare credentials should be supplied through `.env` or the process environment instead of committed config files:

```dotenv
TUSHARE_TOKEN=your_token_here
```

Do not commit `.env`; only `.env.example` belongs in version control.

## Runtime directories

The platform writes generated artifacts to local runtime directories by default:

- `cache/` for downloaded or normalized market data
- `report/` for backtest, admission, and preflight artifacts
- `logs/` for local logs

These directories should stay out of version control.

## Related references

- [Security baseline](../SECURITY_BASELINE.md)
- [Operations runbook](../OPERATIONS_RUNBOOK.md)
