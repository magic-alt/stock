# FastAPI v2 Authentication & Authorization

This document defines the Gate 0 security contract for the production FastAPI v2 surface.

## Security model

FastAPI v2 uses an opaque HTTP Bearer token as the bootstrap authentication mechanism. The server reads the token from `PLATFORM_API_TOKEN`, resolves it to the repository's existing `Subject` / `Role` model, and then evaluates the route's required permission with `Authorizer`.

The bootstrap mechanism is intentionally small. It provides a stable AuthN/AuthZ boundary now while leaving OIDC/OAuth2 or another multi-user identity provider as a later replacement for credential verification. Route permissions and audit semantics do not depend on the future identity provider.

Production behavior is **fail closed**:

- protected route + missing `Authorization` header -> `401`;
- protected route + malformed/invalid Bearer token -> `401`;
- valid token + insufficient RBAC permission -> `403`;
- authentication enabled + `PLATFORM_API_TOKEN` missing -> `503` on protected routes;
- anonymous routes such as health and OpenAPI remain available.

Authentication can only be disabled explicitly with `PLATFORM_API_AUTH_DISABLED=1`. This switch is intended for trusted local development and tests, not externally reachable deployments.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `PLATFORM_API_TOKEN` | empty | Opaque bootstrap Bearer credential. Required for protected routes unless auth is explicitly disabled. |
| `PLATFORM_API_AUTH_DISABLED` | `0` | Set to `1/true/yes/on` only for trusted local-development mode. |
| `PLATFORM_API_TOKEN_SUBJECT` | `bootstrap-admin` | Audit/RBAC subject identifier associated with the bootstrap token. |
| `PLATFORM_API_TOKEN_ROLE` | `admin` | Existing RBAC role: `admin`, `trader`, `viewer`, `strategy`, or `system`. |
| `PLATFORM_API_TOKEN_ACCOUNT_GROUP` | empty | Optional subject account-group scope for future/finer resource isolation. |
| `PLATFORM_API_TOKEN_STRATEGY_ID` | empty | Optional strategy scope. |
| `PLATFORM_API_TOKEN_ACCOUNT_ID` | empty | Optional account scope. |
| `PLATFORM_AUDIT_LOG` | `./logs/audit.log` | Hash-chain audit log used for protected API actions and denials. |

Example production startup:

```bash
export PLATFORM_API_TOKEN="$(python -c 'from src.core.security import generate_api_token; print(generate_api_token())')"
export PLATFORM_API_TOKEN_SUBJECT="ops-admin"
export PLATFORM_API_TOKEN_ROLE="admin"
python -m uvicorn src.platform.api_v2:app --host 0.0.0.0 --port 8000
```

Do not commit the generated token to source control or configuration examples.

Client request:

```bash
curl -H "Authorization: Bearer $PLATFORM_API_TOKEN" \
  http://127.0.0.1:8000/api/v2/gateway/status
```

## Permission model

The API boundary reuses `src/core/auth.py`; it does not define a second RBAC implementation.

Gate 0 adds application permissions needed to classify the v2 surface:

- `data.write`
- `research.execute`
- `job.manage`
- `portfolio.allocate`
- `monitor.query`

Existing trading/account permissions remain authoritative:

- `gateway.connect`
- `gateway.trade`
- `order.query`
- `account.query`
- `position.query`
- `account.manage`
- `fund.transfer`

The default bootstrap token uses the `admin` role. Operators can assign a narrower role with `PLATFORM_API_TOKEN_ROLE`.

## Protected route groups

| Surface | Representative routes | Permission |
|---|---|---|
| Data mutation | `POST /api/v2/local-data/update` | `data.write` |
| Research execution | analysis/backtest runs and submissions, strategy validation | `research.execute` |
| Job control | backtest cancellation | `job.manage` |
| Gateway lifecycle | connect/disconnect | `gateway.connect` |
| Trading mutation | order/cancel/price | `gateway.trade` |
| Trading reads | gateway status/orders/trades/snapshot | `order.query` |
| Account/position reads | gateway account/positions, account list/risk | `account.query` / `position.query` |
| Account mutation | account creation | `account.manage` |
| Cash movement | account transfer | `fund.transfer` |
| Portfolio allocation | capital-allocation preview | `portfolio.allocate` |
| Operations | metrics/monitor endpoints | `monitor.query` |

Health/readiness/info, OpenAPI documentation, strategy catalogue, public market-data reads, analysis capability discovery, and static frontend assets remain anonymous by design.

## Audit subject propagation

For every protected request, the authentication boundary attaches the resolved `Subject` to `request.state.auth_subject`. Authorization denials are written to the hash-chain audit log. Successful state-changing operations are also audited with:

- subject identifier;
- action and resource path;
- required permission;
- request/trace identifiers when available;
- success/error/denied result.

Request payloads and Bearer credentials are intentionally excluded from the audit record to avoid leaking secrets or broker credentials.

## OpenAPI

`/api/v2/openapi.json` publishes the `BearerAuth` HTTP security scheme. Every protected operation carries:

```json
"security": [{"BearerAuth": []}]
```

and declares `401` / `403` responses. Anonymous routes do not carry the security requirement.

## Local development

For a trusted workstation-only workflow:

```bash
PLATFORM_API_AUTH_DISABLED=1 python webui.py --no-open
```

The override is explicit and auditable. Protected actions executed in this mode use the synthetic `local-dev` system subject in the API audit log.

Do not use the disabled mode on a service bound to an untrusted interface.

## Gate 0 acceptance contract

The authentication PR is considered complete when CI proves all of the following:

1. unauthenticated `POST /api/v2/gateway/order` returns `401`;
2. invalid token returns `401`;
3. a valid low-privilege subject receives `403` for an unauthorized mutation;
4. a valid admin token reaches a protected mutation;
5. a protected successful action records the authenticated subject in the hash-chain audit log;
6. OpenAPI advertises `BearerAuth` only for protected routes;
7. the explicit local-development override remains available for legacy/local workflows.

The next ROADMAP item after this contract is merged is **Gate 0 / PR 2 — Deployment correctness + real readiness**.
