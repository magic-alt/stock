# Architecture Overview

Unified Quant Platform uses a modular monolith architecture with clear boundaries between presentation, application, domain, and infrastructure layers.

## Main surfaces

- CLI and GUI entry points
- FastAPI v2 platform API
- Vue3 web console
- Backtest engines and strategy registry
- Trading gateway adapters
- Risk, audit, monitoring, and admission subsystems

## References

- [V6 open-platform proposal](open-platform.md)
- [Platform guide](../PLATFORM_GUIDE.md)
- [Architecture review](../ARCHITECTURE_REVIEW.md)
- [Target architecture](../ARCHITECTURE_TARGET_STATE.md)