# Repository Guidelines

## Project Structure & Module Organization
- `src/`: core library code (`backtest/`, `data_sources/`, `strategies/`, `pipeline/`, `simulation/`, `gateways/`, `core/`).
- `tests/`: pytest suite and coverage guidance.
- `scripts/`: runnable helpers (GUI in `backtest_gui.py`, ops tools like `health_check.py`).
- `docs/`, `examples/`: documentation and runnable examples.
- `config.yaml.example`: configuration template; `cache/` and `report/` store runtime data and outputs.

## Build, Test, and Development Commands
- Install deps: `pip install -r requirements.txt`.
- Run CLI backtest: `python unified_backtest_framework.py run --strategy macd --symbols 600519.SH`.
- Run GUI: `python scripts/backtest_gui.py`.
- Configure: copy `config.yaml.example` to `config.yaml` and edit provider, dates, and risk settings.

## Coding Style & Naming Conventions
- Python PEP 8, 4-space indent, and line length 120 (see `.pre-commit-config.yaml`).
- Use type hints (`typing`) and Google-style docstrings (per README contribution guide).
- Format/lint: `black`, `isort`, `flake8`, `mypy` via pre-commit (`pre-commit install`).
- Naming: modules `snake_case.py`, classes `PascalCase`, tests `tests/test_*.py`.

## Testing Guidelines
- Framework: `pytest` (see `pytest.ini` and `tests/README.md`).
- Run all tests: `python -m pytest tests/ -v`.
- Coverage report: `python -m pytest tests/ --cov=src --cov-report=html`.
- Markers available: `integration`, `slow` (use `-m integration`).
- Coverage target in docs is >95% overall; keep new features covered.

## Branch & PR Workflow (Mandatory)
- **Never commit directly to `main`.** Every new task — features, fixes, refactors, docs — must happen on a dedicated branch.
- Branch naming: `feature/<short-slug>` for new work, `fix/<short-slug>` for bug fixes, `docs/<short-slug>` for pure documentation. Slugs are lowercase, hyphen-separated, and concise (e.g. `feature/zipline-engine-and-stubs`).
- One conversation/task = one branch. Bug fixes for an in-flight feature may stay on that feature branch; otherwise cut a new branch from the latest `main`.
- The push target is always the active fork (`origin` = `magic-alt/stock`). Do **not** push to upstream remotes.
- Push the feature branch as soon as it reaches a working checkpoint so the user can review. PRs into `main` are opened **manually by the user** — agents must not auto-merge.
- Before pushing, run the local CI/CD validation described below and ensure it passes.

## Commit & Pull Request Guidelines
- Commit history favors Conventional Commits: `feat:`, `fix:`, `docs:`, `test:`, `chore:` with optional scopes (e.g., `feat(ml): ...`).
- A few historical commits are plain descriptive messages; prefer Conventional Commits for new work.
- For every optimization, update the relevant documentation and record the change in `CHANGELOG.md`.
- PRs should include: short summary, tests run (or reason not run), and doc/CHANGELOG updates for user-facing changes. Add screenshots or sample reports when GUI or visualization output changes.

## Local CI/CD Validation (Mandatory Before Commit)
- **Before every git commit, you MUST run the local CI/CD validation and ensure it passes.**
- Quick test validation: `python -m pytest tests/ -v --tb=short`
- Full local CI pipeline: `powershell -ExecutionPolicy Bypass -File scripts/local_ci.ps1 -Jobs test -SkipInstall`
- Full CI with all jobs: `powershell -ExecutionPolicy Bypass -File scripts/local_ci.ps1 -SkipInstall`
- The local CI script mirrors the GitHub Actions CI/CD pipeline (`.github/workflows/ci.yml`).
- If local CI fails, fix the issues before committing. Never push code that fails local CI.
- When adding tests that depend on optional packages (e.g., `duckdb`, `scipy`, `pyarrow`, `jinja2`), use `pytest.importorskip` or `@pytest.mark.skipif` to skip gracefully when the package is not installed.

## CHANGELOG.md (Mandatory)
- Follow Keep a Changelog + Semantic Versioning; format is `## [Vx.y.z] - YYYY-MM-DD`.
- Always keep `Unreleased` at the top with the latest date; add entries there until a release is cut.
- Record user-facing changes (features, fixes, breaking changes, docs) and notable internal changes.
- Use the standard categories: Added, Changed, Fixed, Deprecated, Removed, Security, Tests (omit empty sections).
- Keep entries concise; avoid large code blocks and exhaustive file lists.
- When `CHANGELOG.md` grows too large, archive older details into `CHANGELOG_ARCHIVE.md` and keep `CHANGELOG.md` as the curated summary.

## Security & Configuration Tips
- Keep API tokens out of VCS; `config.yaml.example` notes `TUSHARE_TOKEN` via environment variable.
- Avoid committing generated data in `cache/`, `report/`, or `logs/`.
