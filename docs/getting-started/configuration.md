# Configuration

Runtime configuration is resolved through one typed `PlatformSettings` boundary with this precedence:

```text
CLI > environment > config.yaml > safe defaults
```

Copy the sample config and edit only the fields that differ from defaults:

```bash
cp config.yaml.example config.yaml
```

On Windows PowerShell:

```powershell
Copy-Item config.yaml.example config.yaml
```

Select another file with `PLATFORM_CONFIG=/path/to/config.yaml` or the API startup script's `--config` option.

## Validate before running

Run the configuration doctor before deployment:

```bash
quant-platform config doctor
quant-platform config doctor --json
```

The diagnostic output shows effective values and their source while redacting secrets.

## Data provider and API tokens

Credentials should be supplied through environment variables or deployment secret stores instead of committed config files:

```bash
export TUSHARE_TOKEN=your_token_here
export PLATFORM_API_TOKEN=your_long_random_api_token
```

Production authentication remains enabled by default. `PLATFORM_API_AUTH_DISABLED=1` is an explicit local-development override, not a production default.

## Runtime directories

The platform writes generated artifacts to local runtime directories by default:

- `cache/` for downloaded or normalized market data and local JobStore state
- `report/` for backtest, admission, and preflight artifacts
- `logs/` for local logs and audit output

These directories should stay out of version control.

## Related references

- [Platform Settings SSOT](../PLATFORM_SETTINGS.md)
- [Deployment readiness contract](../DEPLOYMENT_READINESS.md)
- [Security baseline](../SECURITY_BASELINE.md)
- [Operations runbook](../OPERATIONS_RUNBOOK.md)
