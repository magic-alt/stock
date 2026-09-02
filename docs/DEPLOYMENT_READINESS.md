# Deployment Correctness & Readiness Contract

This document defines the Gate 0 deployment contract for the FastAPI v2 production surface.
It is the operational companion to `API_V2_AUTHORIZATION.md` and the repository audit roadmap.

## Canonical port

The canonical in-container API port is **8000**.

- `Dockerfile`: `ENV PORT=8000`, `EXPOSE 8000`, Uvicorn consumes `PORT`.
- Docker Compose: container port is always `8000`; `PLATFORM_HOST_PORT` may change only the host-side published port.
- Kubernetes Deployment: named container port `http` -> `8000` and `PORT=8000`.
- Kubernetes Service: `port: 8000`, `targetPort: http`.

Do not reintroduce an internal `8080` port. Deployment contract tests intentionally fail if these surfaces drift.

## Liveness versus readiness

The API now exposes three operational endpoints:

| Endpoint | Meaning | Failure semantics | Probe use |
|---|---|---|---|
| `GET /api/v2/live` | Process can serve HTTP | Dependency failures do **not** fail liveness | Kubernetes `livenessProbe` |
| `GET /api/v2/ready` | Instance may receive business traffic | Returns **503** if a mandatory dependency/configuration is unavailable | Kubernetes `readinessProbe`, Docker/Compose/Render health |
| `GET /api/v2/health` | Backward-compatible legacy process-health endpoint | Kept for existing clients/scripts | Compatibility only |

`/api/v2/health` must not be used as a traffic-admission decision anymore.

## Mandatory readiness checks

`/api/v2/ready` reports structured results for:

### 1. API authentication configuration

Production auth is ready only when `PLATFORM_API_TOKEN` is configured.

For trusted local development only, an operator may explicitly set:

```bash
PLATFORM_API_AUTH_DISABLED=1
```

A missing token with authentication enabled makes readiness fail with HTTP 503.

### 2. JobStore

The readiness probe performs a real JobStore read.

Remote stores are fail-closed for traffic admission: if a configured Redis or PostgreSQL store has degraded to the repository's JSON fallback, readiness is **false** even though the process remains alive. This prevents an instance from silently accepting work with the wrong durability/coordination semantics.

### 3. Local DuckDB market-data store

Startup initialization must have succeeded, and readiness performs an active DuckDB `stats()` probe. Import, filesystem, open, or query failures return HTTP 503.

## Docker and Compose

The production image uses the readiness endpoint for its container `HEALTHCHECK`.

Docker Compose also uses `/api/v2/ready`, so the frontend's `depends_on: condition: service_healthy` does not release the UI against an API that is merely alive.

### Default service boundary

The default Compose profile intentionally contains only:

- `api`
- `frontend`

The previous Redis service was removed because it was neither configured as `PLATFORM_JOB_STORE` nor backed by a Python Redis client in the production dependency set. Keeping it would have exposed port 6379 while the API continued using local JobStore state, creating a misleading distributed topology.

Redis/PostgreSQL remain supported JobStore targets in application code, but they should return to deployment manifests only when all of the following are explicit together:

1. the corresponding production client dependency is installed;
2. `PLATFORM_JOB_STORE` selects that backend;
3. fallback policy is intentional;
4. readiness proves the remote backend is actually active;
5. network exposure is internal-only unless there is a separate operational requirement.

Until then, the default deployment is deliberately single-instance/local-durable rather than pretending to be distributed.

Production-style Compose startup requires a token:

```bash
export PLATFORM_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
python scripts/deploy_release.py
```

For an intentionally local-only stack:

```bash
PLATFORM_API_AUTH_DISABLED=1 python scripts/deploy_release.py
```

The release helper now waits for `/api/v2/ready` and only treats HTTP 2xx/3xx as success; 4xx/5xx responses no longer count as a healthy deployment.

## Kubernetes

The checked-in manifest remains deliberately **single replica**. Live trading gateway ownership is process-local and must stay single-writer until shared durable order/account state, leases/fencing, idempotency, and reconciliation are implemented.

### Secret

Create the API token secret before applying the Deployment. The repository contains a shape-only example at `deploy/k8s/platform-api-secret.example.yaml`; do not apply the placeholder unchanged in production.

Example:

```bash
kubectl create secret generic platform-api-secrets \
  --from-literal=api-token="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
```

### Persistent volume

`platform-api-data` is a `ReadWriteOnce` PVC used for:

- SQLite JobStore (`/data/platform/jobs.sqlite`)
- DuckDB market data (`/data/market_data.duckdb`)
- hash-chain audit log (`/data/logs/audit.log`)
- Qlib data root (`/data/qlib_data`)

The default request is 20 GiB and relies on the cluster's default StorageClass. Production operators should size or override this according to dataset retention requirements.

Apply order:

```bash
kubectl apply -f deploy/k8s/platform-api-pvc.yaml
kubectl apply -f deploy/k8s/platform-api-service.yaml
kubectl apply -f deploy/k8s/platform-api-deployment.yaml
```

### Probe contract

- liveness: `GET /api/v2/live` on named port `http`
- readiness: `GET /api/v2/ready` on named port `http`
- both resolve to container port 8000

### Runtime security

The production image uses a stable numeric UID/GID `10001:10001`. Kubernetes enforces:

- `runAsNonRoot: true`
- `runAsUser/runAsGroup: 10001`
- `seccompProfile: RuntimeDefault`
- `allowPrivilegeEscalation: false`
- drop all Linux capabilities
- CPU/memory requests and limits

The root filesystem is not yet read-only because several existing reporting/runtime paths still write below `/app`; converting all mutable paths to explicit volumes is a later hardening item rather than being hidden behind a manifest flag that would break workloads.

## Readiness response example

Ready:

```json
{
  "ready": true,
  "status": "ready",
  "version": "5.0.0",
  "checks": {
    "api_auth": {"ready": true},
    "job_store": {"ready": true},
    "local_market_data": {"ready": true}
  }
}
```

Not ready:

```json
{
  "ready": false,
  "status": "not_ready",
  "checks": {
    "job_store": {
      "ready": false,
      "detail": "configured remote JobStore is running on local JSON fallback"
    }
  }
}
```

The actual response includes additional non-secret metadata such as backend type, record count, DuckDB row count, and configured local paths. Credentials and DSN contents are not returned.

## Contract tests

`tests/test_deployment_readiness_contract.py` locks the following invariants:

- liveness stays 200 while readiness can become 503;
- auth, JobStore, and DuckDB are mandatory readiness checks;
- Redis/PostgreSQL fallback is not production-ready;
- OpenAPI exposes anonymous `/live` and `/ready` operations;
- Dockerfile, Compose, Render, K8s Deployment/Service/PVC/Secret example all agree on the deployment contract;
- the default Compose profile contains only API + frontend and does not reintroduce unwired Redis;
- Kubernetes probes, resources, security context, and persistent-volume wiring remain present;
- the release helper waits for real readiness.

## Gate 0 acceptance criteria

PR 2 is complete when:

1. no production deployment surface routes API traffic to 8080;
2. liveness and readiness have separate semantics;
3. readiness fails on mandatory dependency/configuration failure;
4. Docker/Compose/Render gate on readiness;
5. Kubernetes has liveness/readiness probes, resource bounds, non-root security context, secret-backed API token, and persistent runtime storage;
6. Redis is either actually wired as the selected JobStore or absent from the default deployment profile;
7. deployment contract tests and the repository CI/CD pipeline pass.
