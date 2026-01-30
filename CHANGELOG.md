# Changelog

All notable changes to this project will be documented in this file.
This project follows Keep a Changelog and Semantic Versioning.
Dates use the format YYYY-MM-DD.

## [Unreleased] - 2026-01-31

### Added
- MLOps model registry with JSON persistence and license policy checks (src/mlops/model_registry.py).
- AI signal schema and framework adapter (src/mlops/signals.py, src/mlops/strategy_adapter.py).
- ML data adapter for training/inference pipelines (src/mlops/data_adapter.py).
- Local inference service with batch runner and demo example (src/mlops/inference.py, examples/mlops_inference_demo.py).
- Drift detection and backtest/live consistency checks (src/mlops/validation.py).
- Trading calendar alignment with suspension fill (src/data_sources/trading_calendar.py).
- Data quality checks with JSON/Markdown reports (src/data_sources/quality.py).
- Reproducibility snapshots and report signatures (src/backtest/repro.py).

### Changed
- CLI and report outputs now include snapshots, quality reports, and report signatures.
- Docs and roadmap updated to reflect the new MLOps and data-quality features.
- Roadmap Phase 3.5 tasks marked as completed.

### Tests
- Added coverage for calendar quality and reproducibility snapshots.

## [V3.2.0] - 2026-01-11

### Added
- Live trading gateways for XtQuant/QMT, XTP, and Hundsun UFT (src/gateways/).
- Base live gateway with reconnect, heartbeat, and state sync utilities.
- Symbol and order mappers for broker formats.
- Stub mode for SDK-unavailable environments.
- Live trading API documentation (docs/LIVE_TRADING_API.md).

## [V3.1.0] - 2026-01-11

### Added
- Unified exception hierarchy and error handler utilities.
- Performance utilities (TTL cache, profiling, batch/parallel helpers).
- Core module exports aligned to the new error/performance stack.

## [V3.1.0-alpha.4] - 2025-12-12

### Added
- ML strategy enhancements and examples.

### Changed
- GUI/tooling polish and core cleanup.

## [V3.1.0-alpha.3] - 2025-12-10

### Added
- Trading infrastructure: trading gateway, order manager, risk manager v2, realtime data.

### Tests
- Added coverage for core trading modules.

## [V3.1.0-alpha.2] - 2025-12-10

### Changed
- Logging standardized across core modules.
- Centralized defaults and strategy alias mapping.

## [V3.0.0-beta.4] - 2025-12-03

### Added
- Enhanced strategies collection including ML-enhanced variants.

## [V3.0.0-beta.3] - 2025-12-03

### Added
- Trend pullback enhanced strategy.

## [V3.0.0-beta.2] - 2025-12-03

### Changed
- Strategy optimizations: risk controls, dynamic parameters, signal filtering.

## [V3.0.0-beta] - 2025-12-03

### Added
- Unified logging, context, live gateway stubs, and paper runner v3.

## [V3.0.0-alpha] - 2025-12-03

### Added
- Strategy unification layer, unified interfaces, and PaperGateway v3.

## [Legacy] - pre-2025

Detailed history for V2.x and earlier releases is archived in CHANGELOG_ARCHIVE.md.
