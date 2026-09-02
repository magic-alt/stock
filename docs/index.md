# Unified Quant Platform

Unified Quant Platform is an A-share quant research and backtesting platform with strategy admission gates, paper trading, a web console, and live gateway adapters.

Use this documentation site as the public entry point for installation, first-run workflows, strategy admission, API references, deployment operations, and the current engineering roadmap.

> **Current readiness baseline (2026-09-02):** research/backtesting and paper-trading capable; live-production hardening is still in progress. See the [Repository Audit & Execution Roadmap](REPOSITORY_AUDIT_AND_ROADMAP_2026-09.md) for production blockers, acceptance gates, and the ordered PR plan.

## Start here

- [Quick start](getting-started/quick-start.md): run the CLI, web console, and deterministic demo paths.
- [Strategy admission](guides/strategy-admission.md): promote strategies from baseline registration to admission and paper validation.
- [Web console](guides/web-console.md): understand the Vue3 + FastAPI console surfaces.
- [REST API](api/rest-api.md): inspect the main API v2 endpoints.
- [FastAPI v2 authentication](API_V2_AUTHORIZATION.md): Bearer token, RBAC permissions, audit subject propagation, and 401/403 contract.
- [Deployment readiness](DEPLOYMENT_READINESS.md): canonical port, liveness/readiness semantics, Docker/Kubernetes probes, persistence, and deployment contract tests.
- [Current audit & roadmap](REPOSITORY_AUDIT_AND_ROADMAP_2026-09.md): the governing post-2026-09 hardening plan and release gates.

## Core references

- [Platform guide](PLATFORM_GUIDE.md)
- [Strategy reference](STRATEGY_REFERENCE.md)
- [Operations runbook](OPERATIONS_RUNBOOK.md)
- [FastAPI v2 authentication & authorization](API_V2_AUTHORIZATION.md)
- [Deployment correctness & readiness](DEPLOYMENT_READINESS.md)
- [Current audit & execution roadmap](REPOSITORY_AUDIT_AND_ROADMAP_2026-09.md)
- [Historical/project roadmap](ROADMAP.md)
