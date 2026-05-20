# Installation

## Requirements

- Python 3.10+
- Node.js 20+ for the web console
- Docker Desktop or Docker Engine for container demos

## Python environment

```bash
git clone https://github.com/magic-alt/stock.git
cd stock
pip install -r requirements.txt
```

Optional feature groups are declared in `pyproject.toml`:

```bash
pip install ".[api,dev,docs]"
```

## Frontend environment

```bash
cd frontend
npm ci
npm run build
```

## Related references

- [Deployment guide](../DEPLOYMENT_GUIDE.md)
- [Gateway SDK setup](../GATEWAY_SDK_SETUP.md)
- [Quick deployment guide](../QUICK_START_DEPLOYMENT.md)