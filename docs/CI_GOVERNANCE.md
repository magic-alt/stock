# CI and branch-governance contract

Status: Gate 0 / PR 3 baseline

This document defines which repository checks are release/merge gates, which checks are informational, and the target protection contract for `main`.

## 1. Design goals

The repository advertises Python 3.10, 3.11, and 3.12 support. CI must therefore prove those versions rather than testing only the newest interpreter. Packaging must be tested from a built wheel rather than relying only on imports from the source checkout. Frontend linting must be reproducible from `package-lock.json`. Security failures that have already reached a blocking severity threshold must fail CI instead of being hidden by `continue-on-error` or shell fallbacks.

The branch rule intentionally depends on one stable aggregate check named **`Required Checks`**. Individual CI jobs may evolve without repeatedly changing the repository ruleset, while the aggregate remains fail-closed whenever any required job fails, is cancelled, or is skipped.

## 2. Required checks

`Required Checks` aggregates the following blocking jobs:

| Job | Contract |
| --- | --- |
| `Python Tests (3.10)` | Supported interpreter test gate |
| `Python Tests (3.11)` | Supported interpreter test gate |
| `Python Tests (3.12)` | Supported interpreter test gate |
| `Windows Tests (3.12)` | Windows compatibility gate |
| `Code Quality` | Ruff plus the current MyPy baseline |
| `Security Gate` | High-severity Bandit findings and known Python dependency vulnerabilities are blocking |
| `Frontend Gate` | `npm ci`, HIGH-severity npm audit, ESLint, Vue/TypeScript type check, and production build |
| `Packaging Smoke (3.10/3.11/3.12)` | Build wheel, Twine metadata validation, clean wheel install, CLI smoke |
| `Documentation Gate` | Strict MkDocs build |
| `Docker Validation` | Production image and Compose configuration |
| `Integration Baseline` | Deterministic `integration` marker tests and CLI smoke |
| `Performance Gate` | Existing performance-regression thresholds |

A required upstream job that is `failure`, `cancelled`, or `skipped` makes `Required Checks` fail. This prevents dependency chains from accidentally turning a skipped downstream job into a green merge signal.

## 3. Informational checks

The following checks deliberately do not gate merge yet:

- **Coverage (informational)** — coverage is collected and uploaded, but no repository-wide percentage threshold has been certified yet.
- **Security Baseline (informational)** — Bandit medium-and-higher findings are recorded as an artifact. The required security gate rejects HIGH findings. Existing MEDIUM findings should be remediated or explicitly risk-accepted before progressively raising the blocking threshold.
- **Frontend moderate advisory baseline** — the lockfile currently retains two MODERATE advisories in the ECharts 5 / vue-echarts 7 dependency chain. npm's available remediation moves to ECharts 6.1.0 and is classified as a breaking change, so Gate 0 blocks HIGH/CRITICAL frontend advisories while the ECharts migration is handled as an explicit compatibility upgrade rather than an automated `--force` rewrite.

Informational status must be visible in the job name or documented as a bounded baseline and must never weaken the `Required Checks` aggregate.

## 4. Security enforcement policy

The pre-hardening workflow hid Bandit and dependency-audit exit codes. Gate 0 changes that contract:

1. `pip-audit -r requirements.txt` is fail-closed.
2. `python -m pip check` validates the installed dependency graph where applicable.
3. Bandit HIGH findings are fail-closed.
4. Bandit MEDIUM findings remain a tracked baseline rather than being silently discarded.
5. `npm audit --audit-level=high` runs automatically before frontend lint and is fail-closed for HIGH/CRITICAL advisories.
6. The remaining ECharts/vue-echarts MODERATE advisory is documented rather than bypassed with `npm audit fix --force`.

The cache-key MD5 use in `src/core/performance.py` is non-cryptographic and is marked with `usedforsecurity=False` so that the security gate can distinguish that use from security-sensitive MD5.

## 5. Python support policy

The authoritative supported range remains the root `pyproject.toml`:

```text
requires-python = ">=3.10"
classifiers = 3.10 / 3.11 / 3.12
```

CI therefore executes the Linux test suite and wheel smoke on 3.10, 3.11, and 3.12. Python 3.12 is the primary Windows/runtime validation version.

Python 3.10 tests that parse TOML use the declared `tomli` compatibility dependency because `tomllib` only exists in the standard library from Python 3.11 onward. A future interpreter must not be added to project metadata until CI proves it. Conversely, a supported interpreter must not be removed from CI without changing project metadata and documenting the compatibility decision in the same PR.

## 6. Frontend reproducibility

Frontend validation is a real gate:

```text
npm ci
  -> npm run lint
       -> prelint: npm run security:audit
                    -> npm audit --audit-level=high
       -> eslint . --max-warnings=0
  -> vue-tsc -b --noEmit
  -> npm run build
```

ESLint and its Vue/TypeScript dependencies are pinned in `frontend/package.json` and resolved in `frontend/package-lock.json`. CI must use `npm ci`; it must not fetch an undeclared `npx ...@latest` linter. The `prelint` lifecycle is intentional: every CI or developer invocation of the required lint gate first validates that the installed frontend graph has no HIGH/CRITICAL npm advisory.

## 7. Packaging smoke contract

Source-checkout tests do not prove that the distributable wheel is usable. The packaging matrix therefore:

1. builds a wheel with `python -m build --wheel`;
2. validates metadata using Twine;
3. installs the produced wheel;
4. changes directory outside the repository checkout;
5. resolves the installed `quant-stock` distribution metadata;
6. executes the installed `quant-platform --version` entry point.

This catches missing package data, package-discovery errors, undeclared build failures, and entry-point breakage that ordinary source tests can miss.

## 8. Dependency automation

`.github/dependabot.yml` tracks three ecosystems weekly:

- Python/pip at repository root;
- npm in `/frontend`;
- GitHub Actions.

Updates are grouped by role to reduce PR noise while still passing through the same required CI contract.

## 9. Target `main` ruleset

The machine-readable target is stored at `.github/ruleset-main.example.json`.

The intended repository rule is:

```text
main
  -> pull request required
  -> branch must be up to date with main
  -> review conversations resolved
  -> Required Checks = success
  -> branch deletion prohibited
  -> non-fast-forward/force push prohibited
```

### Single-maintainer review policy

The repository currently has a single default code owner (`@magic-alt`). A mandatory approval count of one would deadlock normal self-authored PRs because an author cannot approve their own PR. Therefore the Gate 0 target uses:

- PR required: yes;
- required status checks: yes;
- required approving reviews: **0**;
- required code-owner review: no;
- review-thread resolution: yes.

When a second maintainer is routinely available, raise required approvals to one and optionally enable code-owner review in a dedicated governance PR.

### Existing disabled ruleset

At Gate 0 start, repository ruleset `pre-pr` (id `16521365`) is disabled and requires one approval but has no required status checks. Do **not** simply enable that rule unchanged for the single-maintainer repository. Replace or edit it to match `.github/ruleset-main.example.json`, and bind the status requirement to the exact context `Required Checks` after that context has completed successfully at least once.

## 10. Activation sequence

Repository settings are external state and are not applied merely by merging a JSON example. The safe activation sequence is:

1. merge PR #48 only after all new required jobs are green;
2. confirm `Required Checks` appears on `main`/the merged PR;
3. open **Settings → Rules → Rulesets**;
4. edit/replace the disabled `pre-pr` ruleset;
5. target `main` only;
6. configure the rules listed in `.github/ruleset-main.example.json`;
7. require the exact status context `Required Checks` and require the branch to be up to date;
8. set enforcement to **Active**;
9. verify `main` reports protection/ruleset enforcement and that a test PR cannot merge while `Required Checks` is pending or failing.

Until step 8 is completed, CI is hardened but branch governance is not fully enforced at the GitHub repository layer.

## 11. Gate 0 completion condition

Gate 0 / PR 3 is complete only when both conditions are true:

- the repository contains and passes the reproducible CI gates defined above; and
- GitHub reports an active rule protecting `main` with `Required Checks` required.

After that, the strict ROADMAP moves to **Gate 1 / PR 4 — Typed settings SSOT**.
