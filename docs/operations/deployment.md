# Deployment

The project supports local CLI usage, a FastAPI + Vue web console, Docker, Docker Compose, and Kubernetes manifests.

## Production deployment contract

The current Gate 0 deployment contract is documented in [Deployment Correctness & Readiness](../DEPLOYMENT_READINESS.md). That document is authoritative for internal ports, probes, required runtime configuration, Kubernetes persistence/security settings, and deployment acceptance checks.

The canonical API container port is **8000**.

Operational probes have distinct semantics:

- `GET /api/v2/live` — process liveness only;
- `GET /api/v2/ready` — traffic readiness; returns HTTP 503 when a mandatory dependency or production configuration is unavailable;
- `GET /api/v2/health` — backward-compatible process-health endpoint for older clients, not a traffic-admission gate.

## Docker Compose

Production-style Compose startup requires an API token:

```bash
export PLATFORM_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
docker compose up --build
```

The API is exposed on `http://localhost:8000` and the web console on `http://localhost:3000`. The frontend starts only after the API passes `/api/v2/ready`.

The default Compose profile intentionally contains only the API and frontend. The previously unwired Redis container was removed rather than presenting a false distributed JobStore topology. Redis/PostgreSQL JobStore deployment should be enabled only when the corresponding client dependency and explicit backend configuration are present.

For a trusted workstation-only stack, authentication may be disabled explicitly:

```bash
PLATFORM_API_AUTH_DISABLED=1 docker compose up --build
```

Do not use the auth-disabled mode on an externally reachable deployment.

## Kubernetes

The checked-in Kubernetes manifests use:

- container/service port `8000`;
- `/api/v2/live` for `livenessProbe`;
- `/api/v2/ready` for `readinessProbe`;
- Secret-backed `PLATFORM_API_TOKEN`;
- non-root UID/GID `10001` with RuntimeDefault seccomp and dropped capabilities;
- CPU/memory requests and limits;
- a `ReadWriteOnce` PVC for the current single-writer runtime state.

Create the API Secret before applying the Deployment. See `deploy/k8s/platform-api-secret.example.yaml` for the expected shape, but never deploy the placeholder value unchanged.

## References

- [Deployment correctness & readiness](../DEPLOYMENT_READINESS.md)
- [FastAPI v2 authentication](../API_V2_AUTHORIZATION.md)
- [Deployment guide (legacy/reference)](../DEPLOYMENT_GUIDE.md)
- [Quick deployment guide (legacy/reference)](../QUICK_START_DEPLOYMENT.md)
- [Kubernetes manifests](https://github.com/magic-alt/stock/tree/main/deploy/k8s)
