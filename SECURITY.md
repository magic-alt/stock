# Security Policy

## Supported versions

Security fixes are accepted for the current `main` branch and the latest tagged release. Older experimental branches may not receive backports.

## Reporting a vulnerability

Please report security issues privately through GitHub Security Advisories for `magic-alt/stock` when available. If advisories are unavailable, open a minimal issue that describes the affected area without publishing exploit details, and ask the maintainers for a private disclosure channel.

Include:

- Affected component or file path
- Impact and prerequisites
- Reproduction steps or proof of concept, if safe to share privately
- Suggested mitigation, if known

## Scope

In scope:

- Authentication, authorization, tenant isolation, and API access control
- Secret handling and credential leakage
- Trading gateway safety checks and order submission guardrails
- Audit-log integrity and tamper evidence
- Dependency vulnerabilities with practical exploitability

Out of scope:

- Market losses, strategy performance, or investment outcomes
- Vulnerabilities that require already-compromised local machines
- Issues in third-party broker SDKs that cannot be mitigated in this repository

## Secret handling

Keep broker credentials, API tokens, account IDs, and private deployment config out of version control. Prefer environment variables such as `TUSHARE_TOKEN` and deployment secret stores.