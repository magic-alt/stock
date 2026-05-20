# Configuration

Copy the sample config and edit the fields for your local data source, cache directory, and gateway settings.

```bash
cp config.yaml.example config.yaml
```

On Windows PowerShell:

```powershell
Copy-Item config.yaml.example config.yaml
```

## Data provider tokens

TuShare credentials should be supplied through the environment instead of committed config files:

```bash
export TUSHARE_TOKEN=your_token_here
```

## Runtime directories

The platform writes generated artifacts to local runtime directories by default:

- `cache/` for downloaded or normalized market data
- `report/` for backtest, admission, and preflight artifacts
- `logs/` for local logs

These directories should stay out of version control.

## Related references

- [Security baseline](../SECURITY_BASELINE.md)
- [Operations runbook](../OPERATIONS_RUNBOOK.md)