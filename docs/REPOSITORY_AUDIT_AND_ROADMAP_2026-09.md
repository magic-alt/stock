# Repository Audit & Execution Roadmap — 2026-09

> Repository: `magic-alt/stock`  
> Audit baseline: `main@27823afa06861e598cbaf2051d2915b1791d645c`  
> Audit date: 2026-09-02  
> Scope: environment and packaging, documentation, API contracts, security, data/trading workflows, frontend, testing/CI, deployment, repository governance, and architecture robustness.

## 1. Executive summary

The repository has moved well beyond a research-script codebase. It already contains a sizeable A-share research/backtesting stack, strategy admission gates, paper/live gateway abstractions, FastAPI v2, a Vue 3 console, data-lake and DuckDB paths, audit/RBAC primitives, job orchestration, Docker/Kubernetes assets, package facades, and a broad test suite.

The main problem is now **readiness convergence**, not feature count. Several production-facing surfaces still disagree with each other: v1 vs v2 authentication, Docker vs Kubernetes ports, YAML config vs environment-driven runtime configuration, historical ROADMAP claims vs current implementation, and CI reports vs actual merge-blocking gates.

### Current maturity assessment

| Area | Assessment | Notes |
|---|---|---|
| Research / backtesting | **Strong** | Broad strategy/backtest surface, reproducibility/admission concepts, tests and reports are already meaningful. |
| Paper trading | **Good, hardening needed** | Gateway/risk path exists; operational and API boundaries still need tightening. |
| Live trading adapters | **Feature-present, environment-dependent** | Real broker SDKs and accounts remain external dependencies; end-to-end live certification is not represented by CI. |
| FastAPI v2 | **Functionally broad, production gate not closed** | Trading/account/data mutation endpoints are present, but v2 authentication is not enforced. |
| Frontend | **Usable product surface, engineering gates incomplete** | Build/typecheck are in CI; lint script is declared without a complete ESLint toolchain and is not enforced. |
| Deployment | **Docker viable; K8s manifest currently inconsistent** | Production image defaults to port 8000 while current K8s manifests target 8080. |
| Observability | **Good primitives, incomplete readiness semantics** | Metrics/tracing primitives exist; readiness currently returns true unconditionally. |
| CI / governance | **Broad checks, weak enforcement** | Multiple important checks are non-blocking; `main` is unprotected and the repository ruleset is disabled. |
| Documentation | **Extensive, but multiple sources of truth drift** | Existing ROADMAP/status docs contain mutually contradictory statements about implemented capabilities. |

### Readiness conclusion

The repository should currently be described as:

> **Research/backtesting and paper-trading capable; live-production hardening is still in progress.**

It should **not** be represented as fully production-ready for externally reachable live-trading workloads until Gate 0 below is complete.

---

## 2. Audit methodology and confidence levels

This audit reconciles the repository tree, current `main` implementation, configuration files, CI workflows, deployment manifests, public documentation, and repository settings at the baseline commit above.

Findings use three confidence levels:

- **Confirmed** — directly observable from current source/configuration and does not require a broker or external service.
- **Static-risk** — source strongly indicates a defect/risk, but a runtime regression test should be added before closing the item.
- **Environment-dependent** — requires broker SDK, credentials, external data service, cluster, or production-like infrastructure to certify.

This document is the **governing execution roadmap for work after 2026-09-02**. Older roadmap/status documents remain useful historical records, but where they disagree with this audit, the current implementation plus this document take precedence until those documents are consolidated.

---

# 3. Priority findings

## P0 — production blockers

### P0-1 — FastAPI v2 has no effective authentication boundary

**Status: Confirmed**

The production Docker entrypoint runs `src.platform.api_v2:app`. The v2 application exposes state-changing endpoints including:

- `/api/v2/local-data/update`
- `/api/v2/analysis/jobs`
- `/api/v2/backtest/run`
- `/api/v2/backtest/jobs`
- `/api/v2/gateway/connect`
- `/api/v2/gateway/disconnect`
- `/api/v2/gateway/order`
- `/api/v2/gateway/cancel`
- `/api/v2/gateway/price`
- `/api/v2/accounts`
- `/api/v2/accounts/transfer`
- `/api/v2/portfolio/capital-allocation/preview`

`PLATFORM_API_TOKEN` is implemented/documented for the legacy `/api/v1` server path. The Vue client can attach a Bearer token, but the current FastAPI v2 module does not define an HTTP Bearer/OAuth2 security dependency or enforce that token on these routes.

**Risk**

If v2 is exposed outside a trusted localhost/private-development boundary, a caller can reach trading/account/data mutation operations without application-level authentication.

**Required fix**

1. Add a single v2 authentication dependency and OpenAPI security scheme.
2. Preserve `PLATFORM_API_TOKEN` as the backward-compatible bootstrap mechanism.
3. Protect all mutation routes by default; explicitly classify any anonymous read-only routes.
4. Make authentication disablement an explicit local-development setting rather than implicit behavior.
5. Add 401/403 contract tests for every protected router group.
6. Add audit subject propagation from authentication into trading/account operations.
7. Only after token auth is stable, consider optional OIDC/OAuth2 for multi-user deployment.

**Acceptance gate**

- Unauthenticated `POST /api/v2/gateway/order` returns 401.
- Invalid token returns 401/403.
- Valid token reaches authorization/RBAC and produces an auditable subject.
- OpenAPI documents the security requirement.

---

### P0-2 — Kubernetes service port does not match the production container

**Status: Confirmed**

The production Docker command starts Uvicorn on `${PORT:-8000}`. The checked-in Kubernetes Deployment exposes container port `8080`, and the Service targets `8080`, without setting `PORT=8080`.

**Impact**

The checked-in K8s manifest is not a reliable deployment specification for the current production image; the Service can target a port on which the container is not listening.

**Required fix**

- Standardize the production HTTP port (recommended: 8000 to match the current Docker/runtime path), or set `PORT=8080` explicitly in K8s.
- Add `readinessProbe` and `livenessProbe`.
- Add CPU/memory requests and limits.
- Add `securityContext` consistent with the non-root Docker user.
- Replace `emptyDir` for state that must survive pod replacement.
- Add a CI manifest smoke test that verifies container/service/probe ports agree.

---

### P0-3 — readiness endpoint is not a readiness check

**Status: Confirmed**

`/api/v2/ready` returns `{"ready": true}` unconditionally. At startup, DuckDB initialization can fail and is recorded in application state, yet readiness does not reflect that condition. Docker Compose also uses `/api/v2/health` rather than readiness for its healthcheck.

**Risk**

Deployment systems can route traffic to an instance whose required stateful dependencies are unavailable or incorrectly initialized.

**Required fix**

Separate the semantics:

- **liveness**: process/event loop is alive; no downstream dependency checks.
- **readiness**: required JobStore and local data store can initialize/read/write; configured mandatory dependencies are available.
- **dependency status**: detailed diagnostic endpoint for operators, not necessarily the load-balancer probe.

Use readiness in Compose/K8s orchestration and retain liveness for restart decisions.

---

### P0-4 — merge governance does not enforce the repository's own quality gates

**Status: Confirmed**

`main` is currently unprotected. A repository ruleset exists but is disabled. Therefore even the checks that do run can be bypassed by direct merges/pushes.

**Required fix**

Enable a main-branch ruleset with at minimum:

- pull request required;
- required status checks;
- branch must be up to date before merge;
- conversation resolution required;
- force-push/delete disabled;
- CODEOWNERS/review requirement when additional maintainers exist.

Start with checks that are deterministic before promoting flaky/external checks to required status.

---

# 4. P1 — high-priority engineering debt

## P1-1 — dependency and environment declarations lack a single source of truth

**Status: Confirmed**

The repository currently carries overlapping dependency definitions in:

- `pyproject.toml`
- `requirements.txt`
- `requirements-mlops.txt`
- `constraints.txt`
- direct package additions inside `Dockerfile`
- multiple package manifests under `packages/`

`constraints.txt` still identifies itself as a V4.0-A CI seed while the root package is V5.0.0 and the architecture documentation is already discussing V6 phases.

The CI install command also falls back from `pip install ".[api,perf,dev]"` to `requirements.txt`, which can allow a broken package/extras definition to be hidden by the fallback.

**Required direction**

- Make `pyproject.toml` the authoritative dependency declaration for the root distribution.
- Generate/maintain deterministic lock or constraints artifacts from that source.
- Remove ad-hoc runtime dependencies from Docker build commands.
- Add isolated wheel-build + wheel-install smoke tests.
- Test every advertised Python version, or narrow the advertised support range.

**Target CI matrix**

- Linux: Python 3.10, 3.11, 3.12.
- Windows: at least the oldest and newest supported Python.
- One isolated packaging job: build wheel/sdist, install wheel, import main packages, invoke `quant-platform --help`.

---

## P1-2 — important CI checks report failures but do not block regressions

**Status: Confirmed**

Current examples include:

- coverage job marked `continue-on-error`;
- Bandit marked `continue-on-error`;
- pip-audit uses failure suppression and `continue-on-error`;
- integration tests are both failure-tolerant and `continue-on-error`;
- MyPy checks only a very small subset of the codebase;
- frontend build/typecheck runs, but frontend lint is not run.

**Required direction**

Classify CI jobs as either:

1. **Required gate** — deterministic failure blocks merge.
2. **Informational signal** — explicitly named as non-blocking.

Do not present an informational check as a security/integration gate.

Recommended first required set:

- unit/contracts tests;
- strategy smoke gate;
- Ruff;
- frontend typecheck/build;
- MkDocs strict build;
- Docker build + Compose config;
- packaging smoke test;
- focused API security contract tests after P0-1 lands.

Then promote dependency/security and integration checks once baselines/exceptions are explicit.

---

## P1-3 — Compose ships an externally published Redis that the API does not use by default

**Status: Confirmed**

The Compose file publishes `6379:6379` and starts Redis without an application-specific authentication layer. The API service does not set `PLATFORM_JOB_STORE` to the Redis service, so the v2 app continues to use its default local JobStore path unless the operator supplies another value.

**Required fix — choose one design intentionally**

**Option A, recommended for the platform Compose profile**

- Set `PLATFORM_JOB_STORE=redis://redis:6379/<db>`.
- Keep Redis on the internal Compose network only; remove the host port.
- Make failure behavior explicit (`fallback=false` in production profile).

**Option B, recommended for the smallest local demo**

- Remove Redis from default Compose.
- Add it only through an opt-in distributed/production profile.

---

## P1-4 — runtime configuration has multiple competing paths

**Status: Confirmed**

`config.yaml.example` declares `platform.job_store` and `platform.job_store_fallback`, while `api_v2.create_app()` constructs the JobStore from environment variables directly. Several older blocks in the example are also labeled V4.0.

**Risk**

An operator can edit the documented YAML configuration and reasonably expect the API runtime to honor it when it does not.

**Required direction**

Create a typed `PlatformSettings`/Pydantic Settings layer with explicit precedence:

`CLI > environment > config.yaml > safe defaults`

All application factories, workers, gateways, and deployment manifests should consume that same settings object. Add a `quant-platform config doctor` command that prints effective non-secret configuration and validates incompatible settings.

---

## P1-5 — API success/error contracts remain split between v1 and v2

**Status: Confirmed**

The frontend already contains compatibility logic for both:

- legacy `code/message/data/request_id` responses;
- v2 `ok/data/error/request_id` responses.

FastAPI exceptions still use the framework's `detail` response unless specially handled, so even within v2 there is not one typed error envelope. Many routes return an unparameterized `ApiEnvelope`, weakening generated OpenAPI schemas.

**Required direction**

- Freeze one v2 envelope/error contract.
- Add global exception handlers for domain/validation/auth/conflict/not-found errors.
- Define typed response models by router/use case.
- Generate or validate frontend API types from `openapi.json` instead of manually allowing multiple envelope shapes indefinitely.
- Publish explicit v1 deprecation and removal policy.

---

## P1-6 — in-process service ownership must be explicit before horizontal scaling

**Status: Static-risk**

`create_app()` constructs process-local `JobQueue`, `GatewayService`, `MonitorService`, `AccountManager`, metrics, and runtime contexts. This is valid for a modular monolith with one process, but it is unsafe to assume those singletons become shared state when the API is scaled to multiple Uvicorn workers or multiple pods.

**Required architecture rule**

Until state/control planes are externalized:

> **Live trading gateway ownership must be single-writer and single-process.**

Do not scale live order-routing by adding generic API workers. Separate read/query scale from trading-control ownership, or move order/account/job state to transactional shared services with explicit leader/lease semantics.

**Acceptance gate before multi-worker live mode**

- exactly-once/idempotent client order key;
- shared durable order state;
- single active gateway owner per broker account;
- failover lease/fencing token;
- reconciliation after owner change;
- audit continuity.

---

## P1-7 — frontend lint contract is declared but not reproducible

**Status: Confirmed**

`frontend/package.json` defines `npm run lint` using ESLint, but the checked-in dev dependencies do not include ESLint tooling and CI does not run the lint script.

**Required fix**

- Add and pin the Vue/TypeScript ESLint toolchain and config, or remove the non-functional script.
- Run it in CI.
- Add frontend unit tests for API client/envelope/auth handling; add a small Playwright smoke suite for Dashboard → Backtest → Trading paper mode.

---

## P1-8 — documentation status is not a reliable source of truth

**Status: Confirmed**

Examples in the current ROADMAP include mutually incompatible statements that pre-trade live risk integration is:

- still a TODO;
- already completed via `GatewayService`/`RiskManagerV2`;
- still P0 technical debt where Live only performs post-trade auditing.

Current code imports and invokes the common pre-trade risk evaluator in `TradingGateway`, so the documentation needs to be reconciled around the implementation and remaining **real-broker certification**, not re-list the same completed implementation task.

**Required direction**

- Use this audit as the current roadmap SSOT.
- Convert older architecture/status documents to clearly labeled historical design records where appropriate.
- Keep one capability matrix with `implemented / tested / production-certified` as separate columns.
- Do not use a single green checkmark to mean all three.

---

# 5. P2 — maintainability and product-completeness work

## P2-1 — split the FastAPI composition module into routers and application services

`src/platform/api_v2.py` is already a large cross-domain composition module. It owns application startup, middleware, models, data endpoints, analysis, strategies, backtests, gateway trading, accounts, portfolio, monitoring, static frontend serving, and error mapping.

Keep the modular-monolith architecture, but split by responsibility:

```text
src/platform/api_v2/
  app.py
  dependencies.py
  auth.py
  errors.py
  routers/
    operations.py
    data.py
    analysis.py
    strategies.py
    backtests.py
    trading.py
    accounts.py
    portfolio.py
    monitoring.py
  schemas/
```

Route handlers should call application services; they should not reach into private service methods or construct domain infrastructure ad hoc.

**Do not microservice this repository yet.** The current priority is stable contracts, ownership, durability, and observability inside the modular monolith. Premature service decomposition would multiply those unresolved boundaries.

---

## P2-2 — remove user-visible GUI no-op actions

`scripts/backtest_gui.py` currently contains TODO implementations for configuration save/load while reporting success-style log messages.

Either implement typed config serialization/deserialization or disable/label those actions as unavailable. User-facing no-op success paths are higher priority than adding new GUI features.

---

## P2-3 — clean stale API capability claims

The FastAPI v2 module docstring claims REST + WebSocket endpoints and OAuth2 support, but the current module does not expose an application WebSocket route or an OAuth2/Bearer enforcement layer.

Documentation/docstrings should distinguish:

- realtime market-data provider WebSocket clients;
- browser/server WebSocket API;
- future OAuth2/OIDC support;
- current token authentication once P0-1 lands.

---

## P2-4 — strengthen security headers and edge-proxy assumptions

After authentication is fixed:

- define CSP for the SPA;
- add Permissions-Policy;
- confirm HSTS behavior behind trusted proxy headers;
- remove reliance on deprecated `X-XSS-Protection` as a meaningful security control;
- set trusted-host/proxy policy for internet-facing deployments;
- add rate limiting and payload-size limits to expensive/mutating endpoints where appropriate.

---

## P2-5 — package-boundary tests for the V6 facades

The repository now contains multiple `quant_platform_*` distribution facades while retaining `src.*` compatibility paths.

Add automated checks that:

- every distribution builds independently;
- declared dependencies are sufficient;
- facade imports do not rely on undeclared root-package side effects;
- deprecation shims are versioned and tested;
- plugin entry-point discovery works from installed wheels, not only from a source checkout.

---

# 6. What is already strong and should be preserved

The hardening roadmap should not trigger a rewrite. Preserve and deepen these assets:

1. **Strategy admission concept** — the staged research → baseline → admission → paper → live-candidate model is a meaningful differentiator.
2. **A-share domain rules** — T+1, lot size, price limits, suspension/calendar/data adjustments belong in explicit domain contracts.
3. **Unified pre-trade risk path** — keep one evaluator shared by paper/live/order-manager paths and certify it against real adapters.
4. **Broad test inventory** — the repository already has API, risk, audit, fault/load, engine, and contract tests; the next step is classification and enforcement, not test-framework replacement.
5. **Non-root production image** — keep the container security baseline while making dependencies and probes reproducible.
6. **Modular-monolith direction** — V6 engine/adapter/runtime/package boundaries are a better next step than premature microservices.
7. **Deterministic paper path** — continue using broker-independent paper mode for CI and contributor onboarding.

---

# 7. Target architecture after hardening

```text
Clients
  Vue / CLI / SDK
        |
        v
FastAPI v2 edge
  AuthN -> AuthZ/RBAC -> request/trace/audit context
        |
        +-----------------------+
        | Application Services  |
        | data / research       |
        | backtest / admission  |
        | trading / accounts    |
        | monitoring            |
        +-----------------------+
             |           |
             v           v
        Runtime/Engines  Durable control state
             |           JobStore / order/account ledger
             v
       Ports / Contracts
             |
      +------+-------+----------------+
      |              |                |
 Data adapters   Broker adapters   Storage/messaging
```

### Architectural invariants

- HTTP is an adapter, not the domain layer.
- API auth and audit subject are resolved before trading mutation.
- One broker account has one active order-routing owner.
- Order/account state required for recovery is durable before horizontal scale.
- Backtests can scale horizontally; live control paths scale by ownership partitioning, not blind worker count.
- Research, paper, and live share contracts/risk rules but have separate runtime safety policies.
- Configuration is typed and resolved once.
- OpenAPI is a tested contract, not incidental documentation.

---

# 8. Execution roadmap

## Gate 0 — Production safety convergence (next PRs)

### PR 1 — FastAPI v2 authentication + authorization contract

**Files likely touched**

- `src/platform/api_v2.py` or new `src/platform/api_v2/auth.py`
- `src/core/auth.py`
- API security tests
- frontend auth store/client
- deployment/security docs

**Deliverables**

- v2 Bearer enforcement;
- OpenAPI security scheme;
- anonymous route allowlist;
- RBAC subject propagation;
- 401/403 tests;
- no secrets logged.

### PR 2 — Deployment correctness + real readiness

**Files likely touched**

- `Dockerfile`
- `docker-compose.yml`
- `deploy/k8s/*`
- `src/platform/api_v2.py`
- deployment tests/docs

**Deliverables**

- one canonical port;
- meaningful readiness;
- K8s probes/resources/security context;
- durable state decision;
- Redis either wired internally or removed from default profile.

### PR 3 — CI and branch-governance hardening

**Files likely touched**

- `.github/workflows/ci.yml`
- `.github/CODEOWNERS` when appropriate
- dependency automation config
- repository ruleset/settings

**Deliverables**

- required vs informational jobs explicitly separated;
- Python support matrix aligned with metadata;
- packaging smoke job;
- frontend lint made real;
- security/integration baseline promoted progressively;
- protected `main`.

**Gate 0 exit criteria**

- [ ] v2 mutation endpoints reject unauthenticated calls.
- [ ] Docker and K8s pass the same readiness/port contract.
- [ ] `main` cannot merge without required checks.
- [ ] clean-clone packaging and frontend checks are reproducible.
- [ ] production documentation no longer describes the current system as generally production-ready without qualification.

---

## Gate 1 — Contract and state convergence

### PR 4 — Typed settings SSOT

- Pydantic settings with documented precedence.
- Remove duplicated/stale versioned config semantics.
- `config doctor` command.
- Docker/Compose/K8s consume the same named settings.

### PR 5 — API contract normalization

- versioned typed response/error schemas;
- domain exception mapping;
- OpenAPI snapshot/contract test;
- generated frontend types/client or schema-drift test;
- formal v1 deprecation timeline.

### PR 6 — Router/application-service decomposition

- split `api_v2.py` by bounded capability;
- dependency injection for services/stores;
- stop calling private service methods from HTTP handlers;
- preserve endpoint compatibility during refactor.

### PR 7 — durable live-control state model

- define durable order/account/gateway-session ownership;
- idempotency keys on order submission;
- transaction/reconciliation semantics;
- single-writer lease/fencing if process/pod failover is introduced.

**Gate 1 exit criteria**

- [ ] one effective configuration model;
- [ ] one v2 response/error contract;
- [ ] API routers are thin adapters;
- [ ] horizontal scaling rules are documented and mechanically enforced;
- [ ] recovery does not depend on one process's in-memory state for certified live paths.

---

## Gate 2 — Product completeness and developer experience

### PR 8 — frontend engineering baseline

- working ESLint configuration;
- frontend unit tests;
- Playwright paper-mode smoke path;
- generated/validated API types.

### PR 9 — GUI truthfulness and configuration UX

- implement or remove no-op save/load;
- share typed config schema with CLI/API where practical;
- add GUI regression tests around builders/config parsing.

### PR 10 — documentation consolidation

- merge superseded status/audit documents into a clear hierarchy;
- capability matrix separates implemented/tested/certified;
- architecture decisions become ADRs;
- README points to one current roadmap and one quick start.

**Gate 2 exit criteria**

- [ ] no user-facing success message for a no-op feature;
- [ ] docs have a clear current/historical distinction;
- [ ] frontend/API contract drift is detected by CI.

---

## Gate 3 — Live-production certification

This gate is intentionally environment-dependent and cannot be certified by mock tests alone.

### PR / certification track

1. **QMT/XtQuant** real SDK integration test harness.
2. XTP/UFT equivalent harness where supported.
3. pre-trade reject tests against adapter boundaries.
4. disconnect/reconnect/order-query reconciliation.
5. duplicate-submit/idempotency and timeout ambiguity handling.
6. trading-day startup/shutdown runbook.
7. audit-chain export and immutable archive policy.
8. latency/throughput baseline with stated hardware/network assumptions.
9. disaster-recovery exercise with measured RTO/RPO.
10. kill switch and operator permission model.

**Gate 3 exit criteria**

A broker adapter is called **production-certified** only when its SDK/version/environment matrix and the scenarios above are recorded. “Adapter implemented” is not equivalent to “live-production certified.”

---

# 9. Suggested issue backlog

| Priority | Issue | Definition of done |
|---|---|---|
| P0 | Protect FastAPI v2 mutation routes | Bearer/RBAC/OpenAPI + negative tests |
| P0 | Fix K8s port/probes | deploy smoke test reaches readiness |
| P0 | Make readiness dependency-aware | failed mandatory store => not ready |
| P0 | Enable main branch ruleset | required checks cannot be bypassed |
| P1 | Dependency SSOT | wheel install and Python matrix pass |
| P1 | Promote CI gates | no hidden `continue-on-error` on required jobs |
| P1 | Decide Redis default role | internal wired backend or remove default service |
| P1 | Typed settings | YAML/env/CLI resolve to one settings object |
| P1 | Normalize v2 errors | one documented typed envelope |
| P1 | Live single-writer ownership | explicit process/pod ownership invariant |
| P1 | Frontend lint/test | clean `npm ci && npm run lint && npm run build` |
| P1 | Reconcile ROADMAP capability claims | implemented/tested/certified split |
| P2 | Split API routers | thin handlers + application services |
| P2 | Fix GUI save/load no-op | functional persistence or feature removed |
| P2 | Package facade build matrix | each distribution independently installable |
| P2 | Security edge hardening | CSP/proxy/rate/payload policies tested |

---

# 10. Release/readiness checklist

## Research release

- [ ] clean install succeeds on supported Python versions;
- [ ] deterministic demo succeeds without broker credentials;
- [ ] strategy/backtest contracts pass;
- [ ] docs build strict;
- [ ] report artifacts include reproducibility metadata.

## Paper-trading release

All Research checks, plus:

- [ ] v2 auth enabled when bound beyond localhost;
- [ ] risk/reject/order lifecycle contracts pass;
- [ ] durable JobStore configured for production-like deployment;
- [ ] readiness reflects required dependencies;
- [ ] restart/recovery test passes.

## Live-production certification

All Paper checks, plus:

- [ ] broker-specific SDK/version is certified;
- [ ] single-writer gateway ownership guaranteed;
- [ ] order idempotency/reconciliation proven;
- [ ] kill switch tested;
- [ ] audit identity and archive tested;
- [ ] incident/rollback/DR drill completed;
- [ ] latency/capacity baseline recorded;
- [ ] no unresolved P0 finding in this audit.

---

# 11. Recommended next action

The strict next item should be **Gate 0 / PR 1: FastAPI v2 authentication + authorization contract**.

Do not start another broad feature tranche before that boundary is closed. The repository already has enough functional breadth; the highest-value engineering work is now to make the production surface truthful, enforceable, recoverable, and testable.
