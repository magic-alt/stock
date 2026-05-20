# Deployment

The project supports local CLI usage, a FastAPI + Vue web console, Docker, Docker Compose, and Kubernetes manifests.

## Docker Compose

```bash
docker compose up
```

The API is exposed on `http://localhost:8000` and the web console on `http://localhost:3000`.

## References

- [Deployment guide](../DEPLOYMENT_GUIDE.md)
- [Quick deployment guide](../QUICK_START_DEPLOYMENT.md)
- [Kubernetes manifests](https://github.com/magic-alt/stock/tree/main/deploy/k8s)