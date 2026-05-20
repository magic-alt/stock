# Contributing

Thanks for helping improve Unified Quant Platform. This project is optimized for small, reviewable pull requests with reproducible local validation.

## Development workflow

1. Create a branch from the latest `main`.
2. Use a scoped branch name such as `feature/open-source-demo`, `fix/mkdocs-nav`, or `docs/quick-start`.
3. Keep unrelated formatting, generated reports, cache files, and local IDE files out of the PR.
4. Use Conventional Commits where practical: `feat:`, `fix:`, `docs:`, `test:`, `chore:`.
5. Open a pull request into `main`; do not commit directly to `main`.

## Local validation

Run the focused checks for the area you changed. Before requesting review, at minimum run:

```bash
python -m pytest tests/ -v --tb=short
python -m mkdocs build --strict
```

For the local CI mirror:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/local_ci.ps1 -Jobs test -SkipInstall
```

Frontend changes should also pass:

```bash
npm --prefix frontend ci
npm --prefix frontend run build
```

## Good first contributions

- Improve quick-start docs or examples.
- Add deterministic demo fixtures that do not require broker SDKs or data-provider tokens.
- Add focused tests for strategy admission, A-share trading rules, or API contracts.
- Clarify stub, mock, and real broker SDK behavior.

## Generated files

Do not commit local runtime outputs from `cache/`, `report/`, `logs/`, `site/`, or editor folders unless a maintainer explicitly asks for a specific artifact.

## Security and credentials

Never commit API tokens, broker credentials, account IDs, private keys, or production config files. Use environment variables and local config files ignored by version control.