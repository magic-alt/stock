# Troubleshooting

## First checks

```bash
python scripts/health_check.py
python -m pytest tests/ -v --tb=short
python -m mkdocs build --strict
```

## Common areas

- Data provider tokens and network access
- Broker SDK availability and stub mode
- Runtime directories under `cache/`, `report/`, and `logs/`
- Docker port conflicts on 8000 or 3000

## References

- [Operations runbook](../OPERATIONS_RUNBOOK.md)
- [Deployment guide](../DEPLOYMENT_GUIDE.md)
- [Gateway SDK setup](../GATEWAY_SDK_SETUP.md)