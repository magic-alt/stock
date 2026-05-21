# Distribution Split

Phase 7 keeps the repository as one monorepo, but defines six independently
buildable Python distributions. The split is packaging-only: legacy imports
under `src.*` remain valid and the new `quant_platform_*` packages are thin
facades over the already implemented modules.

| Distribution | Import facade | Purpose |
|---|---|---|
| `quant-platform-core` | `quant_platform_core` | Kernel, contracts, engines, backtest, simulation, pipeline, indicators, optimizer |
| `quant-platform-sdk` | `quant_platform_sdk` | Plugin author SDK, DTOs, ports, manifests, `PluginRegistry` |
| `quant-platform-adapters-cn` | `quant_platform_adapters_cn` | A-share data, realtime, storage and broker adapter namespace |
| `quant-platform-ml` | `quant_platform_ml` | MLOps, Qlib, FinRL and ML strategy adapter namespace |
| `quant-platform-web` | `quant_platform_web` | FastAPI platform services and web console asset metadata |
| `quant-platform-cli` | `quant_platform_cli` | CLI entry points and scaffolding commands |

Build examples:

```bash
python -m build packages/quant_platform_core
python -m build packages/quant_platform_sdk
python -m build packages/quant_platform_cli
```

The root `quant-stock` package remains the batteries-included distribution for
source installs and local development.
