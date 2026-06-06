## Summary

-

## Related Issues

<!-- Link related issues: Fixes #xxx, Refs #xxx -->

## Validation

<!-- Paste actual command output for key checks -->

- [ ] `python -m pytest tests/ -v --tb=short`
- [ ] `python -m mkdocs build --strict`
- [ ] `npm --prefix frontend run build` (if frontend changed)
- [ ] `docker compose config` / Docker validation (if deployment changed)

## Compatibility & Risk

<!-- Does this change break existing APIs, configs, or database schemas? -->
<!-- Are there third-party dependency version bumps that could affect users? -->

## Rollback Plan

<!-- How to revert if this causes issues in production? -->

## Screenshots or Artifacts

Add screenshots, sample reports, or demo output paths when UI, docs, reports, or visualizations change.