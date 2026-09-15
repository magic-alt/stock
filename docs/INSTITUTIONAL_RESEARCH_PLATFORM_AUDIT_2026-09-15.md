# Institutional Research Platform Audit & Roadmap — 2026-09-15

> Repository: `magic-alt/stock`  
> Audit baseline: `main@3c7d440c616f2a8d408cef7c073803ea3e214854`  
> Previous audit baseline: `27823afa06861e598cbaf2051d2915b1791d645c` (2026-09-02)  
> Scope: release readiness, architecture extensibility, Backtrader coverage, TuShare Pro/A-share research correctness, end-to-end research workflow, documentation and institutional-grade readiness.

---

## 1. Executive decision

The repository has progressed far beyond a collection of Backtrader scripts. It already contains a broad quant-platform skeleton: data providers, factor/strategy modules, a Backtrader-default backtest path, optional alternative engines, paper/live gateways, risk and order-management components, FastAPI/Vue surfaces, data-lake/versioning concepts, plugin contracts, V6 runtime/kernel work, packaging splits and a strong CI workflow.

However, **the current `main` should not be published as a stable `v5.0.0` release and should not yet be described as an institutional-grade A-share research platform**.

The reason is no longer primarily deployment engineering. The 2026-09-02 audit triggered substantial hardening work and the current main CI is green. The remaining release blockers are deeper and more important for a quant platform:

1. release identity/version provenance is inconsistent;
2. TuShare adjusted-price semantics are not trustworthy enough for research;
3. financial factors are not point-in-time safe and can leak future information;
4. the advertised A-share T+1 / price-limit model is not closed in the matching path and is too coarse for modern board-specific rules;
5. Backtrader is the default engine, but the backend abstraction is still partially facade/delegation rather than true ownership of Backtrader execution semantics.

### Release recommendation

**Do not publish current `main` as `v5.0.0`.** The immutable `v5.0.0` tag already points to an older 2026-06-06 commit (`fdac7d75...`), while current main is 156 commits ahead and GitHub Releases is empty.

Recommended sequence:

```text
P0 research/release correctness fixes
        ↓
5.1.0rc1 / v5.1.0-rc.1
        ↓
clean-room install + TuShare fixture E2E + research gates
        ↓
5.1.0 stable
```

The first public pre-release should be treated as a **research-platform RC**, not as proof of institution-grade live-production certification.

---

## 2. Maturity assessment

Scores are audit heuristics, not product marketing metrics. The evidence/exit criteria below govern status.

| Area | Current assessment | Main strengths | Main blockers |
|---|---|---|---|
| Release engineering | **6/10** | broad CI, wheel build/install, docs/docker/security checks, tag-triggered release machinery | `v5.0.0` tag drift, no GitHub Release, auto-tag semantics, version immutability violation |
| Architecture extensibility | **7.5/10** | V6 contracts/ports, plugin registry, kernel/runtime, adapter/engine namespaces, package facades | many canonical namespaces still re-export V5 ownership; important runtime seams remain coupled |
| Backtest/strategy breadth | **8/10** | many Backtrader strategies, analyzers/metrics, fees/sizers, plotting/reporting, optimization utilities | capability contract incomplete; failure semantics and China execution parity need tightening |
| Backtrader extension completeness | **5.5/10** | default engine integrated, unified strategy adapter, commission/sizer support | backend delegates to `BacktestEngine._run_module`; no formal support for much of native resample/replay/order/observer/writer/live surface |
| TuShare Pro integration | **5/10** | daily OHLCV/index provider, caching, token integration, financial provider | qfq path incorrect/ambiguous, no hfq contract, no PIT financial availability, major research datasets absent |
| A-share market realism | **5/10** | explicit A-share rules object, fee/sizer work, suspension/limit concepts | T+1 helper not wired end-to-end; hard-coded 10/5% limits; board/date/state-specific rules incomplete |
| Research validation | **6.5/10** | reproducibility concepts, strategy admission, ML walk-forward example, reports | no platform-wide PIT/leakage audit, purging/embargo/OOS protocol, robustness/multiple-test governance |
| Documentation volume | **8.5/10** | extensive docs, API/architecture/deployment material, examples | status semantics drift; target vs implemented state not always distinguished; capability claims can outrun evidence |
| Institutional research readiness | **6/10** | strong platform skeleton and operational surfaces | data correctness/PIT/universe/reproducibility evidence chain must be closed before institutional claim |

### Practical interpretation

- **Suitable today:** technical-indicator experiments, single-/multi-asset Backtrader research, platform/API development, paper-trading development, architecture/plugin experimentation, non-critical A-share exploratory analysis.
- **Suitable after P0/P1 data work:** reproducible TuShare Pro A-share technical, fundamental, cross-sectional and index-universe research.
- **Not yet justified:** claiming that arbitrary fundamental/multi-factor backtests are PIT-correct; claiming complete Backtrader feature coverage; calling the platform institution-grade solely because many modules exist.

---

## 3. Release-readiness audit

### 3.1 What is already strong

The current CI workflow is substantially stronger than the previous audit baseline. It includes multi-version Python tests, Windows coverage, Ruff, security/dependency checks, frontend lint/typecheck/build, packaging smoke, strict docs build, Docker validation, integration/performance jobs and an aggregate required-check path.

This is enough engineering machinery to support a real release process.

### 3.2 Confirmed version/release defect

`pyproject.toml` still declares `5.0.0`. An annotated `v5.0.0` tag already exists, created by GitHub Actions on 2026-06-06, and points to `fdac7d75e31f89681586a8a7e15a6eaf41f40b2d`.

Current main is 156 commits ahead of that source commit. GitHub Releases is empty.

Therefore the current code cannot legitimately be redefined as the same `5.0.0` release.

**Tracking:** #59

### 3.3 Release exit gate

Stable release must require all of:

- #60 adjusted-price provider correctness;
- #61 PIT financial availability correctness;
- #62 strict A-share execution-rule regression matrix;
- #63 Backtrader capability/parity contract sufficiently complete for advertised scope;
- a clean-room TuShare fixture E2E research run;
- exact code/data/environment manifest in the produced report;
- release artifact build/install from the tagged commit;
- checksum/provenance and GitHub Release object.

---

## 4. Architecture extensibility audit

### 4.1 What the architecture gets right

The V6 direction is sound:

- stable contracts and DTOs;
- `typing.Protocol`-style ports;
- plugin entry-point discovery;
- lifecycle/kernel/runtime composition;
- canonical adapter/engine namespaces;
- split package facades;
- explicit backtest/sandbox/live runtime concepts;
- compatibility/deprecation infrastructure.

This is a better long-term direction than embedding every provider and broker into a single CLI or Backtrader-specific object graph.

### 4.2 Current limitation: namespace convergence != ownership convergence

A large part of V6 deliberately preserves object identity by re-exporting V5 implementations. That is useful for migration, but it is not the final architecture.

The clearest example is Backtrader: `BacktraderBackend` is present but delegates back into `BacktestEngine._run_module()`, while that generic engine still constructs Cerebro, Backtrader analyzers and plotting-specific indicators.

The same migration principle should be applied across research data, market rules, storage and reporting: **ports should own the boundary at runtime, not only in import paths.**

**Tracking:** #66

### 4.3 Recommended architecture rule

Keep the modular monolith. Do not microservice the platform yet.

The target dependency direction should be:

```text
CLI / API / Web
      ↓
Runtime composition roots
      ↓
Application / research services
      ↓
Contracts / Ports
      ↓
Engines  ←→  Adapters
      ↓
Storage / external systems
```

Compatibility shims should be leaves, not dependencies of canonical implementations.

---

## 5. Backtrader audit — is it a complete Backtrader extension?

**No.** It is a meaningful Backtrader-based platform, but it does not currently expose or wrap the full relevant Backtrader surface.

### 5.1 Existing strengths

The platform already uses Backtrader effectively for:

- strategy execution;
- multiple strategy implementations;
- multiple data feeds;
- custom commission/sizer behavior;
- standard analyzers such as returns/Sharpe/drawdown/trades;
- report and plotting integration;
- a unified strategy adapter for a subset of engine-neutral operations.

### 5.2 Confirmed gaps

Repository search on the audit baseline found no formal `resampledata`, `replaydata`, `optstrategy`, `addobserver` or `addwriter` integration path.

The unified strategy adapter exposes market/limit buy/sell, while cancellation currently returns `False`. Richer Backtrader native order semantics are not represented by the engine-neutral interface.

Backtrader itself supports a much broader native surface including resampling, multiple timeframes, replay, analyzers, observers, writers, sizers, richer order types and store/broker based live operation.

The correct product strategy is **not** to wrap every Backtrader API. Instead:

1. publish an explicit capability matrix;
2. define which behaviors are native, wrapped, replaced by platform semantics, or unsupported;
3. move all Backtrader-specific execution ownership behind `BacktraderBackend`;
4. add parity fixtures against the platform simulation contract.

**Tracking:** #63

---

## 6. TuShare Pro audit — can it support serious A-share strategy research?

### 6.1 TuShare Pro itself: yes

TuShare Pro can provide a rich enough A-share data foundation for many research classes when the account has appropriate permissions/points. Relevant datasets include:

- raw daily bars;
- adjustment factors / adjusted bars;
- daily valuation/turnover/market-cap fields (`daily_basic`);
- suspension state (`suspend_d`);
- authoritative daily price bands (`stk_limit`);
- historical index constituents/weights (`index_weight`);
- financial statements and indicators;
- stock/instrument master and listing metadata.

This is enough to support technical, fundamental, cross-sectional, index-universe and portfolio/rebalance research if the platform preserves historical availability correctly.

### 6.2 Current stock integration: not yet research-grade

#### A. Adjusted-price problem

`TuShareProvider` labels qfq datasets but calls `pro.daily(..., adj='qfq')`. The documented TuShare adjusted-bar path is `ts.pro_bar(..., adj='qfq'/'hfq')`, or explicit reconstruction from raw bars + adjustment factors.

Until fixed, returns around corporate actions cannot be trusted simply because the cache key says `qfq`.

**Tracking:** #60

#### B. Fundamental look-ahead problem

`TushareFinancialProvider` indexes several financial endpoints by statement `end_date`, not announcement availability `ann_date`.

That can make future financial information visible to earlier historical decisions.

`RevenueGrowth(period=252)` is also conceptually inconsistent with report-row frequency.

**Tracking:** #61

#### C. Research-domain incompleteness

The platform does not yet expose TuShare Pro as a coherent PIT A-share domain. Key datasets such as `daily_basic`, historical instrument master/listing status, `stk_limit`, `suspend_d` and `index_weight` were not found in the integration.

**Tracking:** #64

### 6.3 Strategy classes after closure

Once #60/#61/#64/#62 are complete, the platform can credibly support:

- MA/MACD/RSI/trend/breakout/mean-reversion strategies;
- volatility and channel strategies;
- value/quality/profitability/growth factor strategies;
- multi-factor ranking;
- CSI 300/500/1000 constituent-aware research;
- sector/industry rotation where classification data is available;
- index enhancement and rebalancing;
- ML ranking/classification/regression workflows;
- portfolio construction and risk-budgeting research;
- event/corporate-action studies if availability timestamps are modeled explicitly.

---

## 7. A-share execution realism audit

### 7.1 T+1 is not closed

`AShareRules.record_buy()` and `sellable_qty()` exist, but no repository call site was found wiring them to fills and sell-order validation. The actual `submit_order()` checks suspension, price limit and lot size, not sellable inventory.

Therefore the current documentation should not treat T+1 as fully implemented in the default matching path.

### 7.2 Price-band model is too coarse

The rule currently derives `10%` or `5% ST` bands. Modern A-share rules are board/date/state dependent:

- STAR: typically 20%, with initial no-limit sessions;
- ChiNext: 20%, with initial no-limit sessions;
- BSE: 30% with its own rules;
- IPO/delisting/relisting/risk-warning sessions have special cases.

Authoritative daily `stk_limit` data is preferable to reimplementing all historical rule transitions from constants.

### 7.3 Required direction

Introduce a PIT `MarketStateService` shared by backtest/paper/pre-trade logic:

```text
is_tradable(symbol, session)
sellable_qty(account, symbol, session)
price_band(symbol, session)
lot_rule(symbol, side, order_type, session)
session_state(symbol, session)
```

**Tracking:** #62

---

## 8. Research methodology audit

The repository contains useful research machinery and an ML walk-forward implementation. That is not equivalent to a platform-wide research protocol.

Institutional research requires defaults that prevent accidental invalid experiments.

### Required common protocol

- time-aware train/validation/test splits;
- purging/embargo where labels overlap;
- PIT feature/universe joins;
- immutable final OOS window;
- cost/slippage/delay sensitivity;
- parameter stability tests;
- regime/sub-period diagnostics;
- turnover/liquidity/capacity diagnostics;
- multiple-testing awareness;
- benchmark and active-risk metrics;
- immutable experiment manifest.

**Tracking:** #65

---

## 9. End-to-end institutional workflow

The repository already has many individual components. Institution-grade quality comes from the chain of evidence, not the count of modules.

Target lineage:

```text
Data source
  -> raw immutable landing
  -> normalized/PIT curated datasets
  -> dataset + universe snapshots
  -> features/signals
  -> experiment definition
  -> backtest runs
  -> robustness/OOS gates
  -> immutable report/artifacts
  -> strategy version
  -> admission evidence
  -> paper validation
  -> live candidate
```

Every promoted strategy must answer:

> Which data snapshot, universe, code SHA, parameters, engine, execution assumptions and validation evidence produced this decision?

**Tracking:** #68

---

## 10. Documentation audit

Documentation is extensive, but institutional documentation must separate five states:

```text
implemented
contract-tested
E2E-tested
research-valid
production-certified
```

A single checkmark cannot safely represent all five.

### Required SSOT capability matrix

Each material capability should link to evidence and known limitations, especially:

- Backtrader capability coverage;
- TuShare Pro dataset coverage;
- A-share market-rule coverage;
- PIT/research-valid status;
- broker/live certification;
- release/package compatibility.

A clean-room TuShare tutorial should prove the entire research path rather than only demonstrating API calls.

**Tracking:** #67

---

# 11. Execution roadmap

## Gate 0 — research correctness + release identity (P0)

**Issues:** #59, #60, #61, #62

### Objective

Make the platform incapable of producing a plausibly successful but semantically invalid A-share research result for the audited failure modes.

### Deliverables

1. explicit release/version workflow;
2. correct raw/qfq/hfq TuShare contract;
3. PIT financial availability model + as-of joins;
4. T+1 fill/inventory closure;
5. board/date/state-aware price/lot/tradability model;
6. deterministic regression fixtures for all above.

### Exit criteria

- all four P0 issues closed with regression tests;
- no stable release while any of these gates is red;
- fixture-based clean-room research run is reproducible from manifest.

---

## Gate 1 — Backtrader/backend and TuShare research domain

**Issues:** #63, #64

### Objective

Turn Backtrader and TuShare from important concrete integrations into clean platform adapters with explicit capability contracts.

### Deliverables

- Backtrader execution fully owned by `BacktraderBackend`;
- documented native/wrapped/replaced/unsupported capability matrix;
- engine-neutral parity fixtures;
- canonical A-share data domain (instrument/calendar/bars/adjustments/daily basics/market state/index membership/PIT financials);
- resumable quota-aware TuShare ingestion and snapshots.

### Exit criteria

- a technical and a cross-sectional strategy run from immutable TuShare snapshots;
- result manifests include dataset, universe, code and execution fingerprints;
- unsupported Backtrader features fail clearly instead of silently degrading.

---

## Gate 2 — institutional research protocol and evidence catalog

**Issues:** #65, #68

### Objective

Make research validation and reproducibility default platform behavior.

### Deliverables

- common split/OOS/leakage/robustness protocol;
- experiment/run/strategy-version evidence model;
- research catalog CLI/API;
- admission linked to immutable evidence IDs;
- comparison/reproduction tools.

### Exit criteria

- deliberately leaked experiments fail tests;
- technical, factor and ML examples share the protocol;
- any `paper_validated` or `live_candidate` strategy can be traced back to exact experiment evidence.

---

## Gate 3 — V6 ownership convergence

**Issue:** #66

### Objective

Make the implemented dependency graph match the V6 target architecture.

### Deliverables

- import/dependency architecture gate;
- real port ownership for backtest/data/market-state/storage/report seams;
- built-in plugin conformance using the same contracts as third-party plugins;
- finite legacy/deprecation plan.

### Exit criteria

- target-state and implemented-state diagrams match for high-value seams;
- architecture tests block layer inversions;
- no new business logic lands only in legacy/facade layers.

---

## Gate 4 — evidence-backed docs and RC/stable release

**Issues:** #67 and #59 finalization

### Objective

Publish only capabilities supported by reproducible evidence.

### Deliverables

- SSOT capability matrix;
- Backtrader support matrix;
- TuShare clean-room guide;
- concise release notes + known limitations;
- `5.1.0rc1` release;
- stable `5.1.0` after RC acceptance.

### Stable release exit criteria

- clean install from wheel/sdist;
- required CI green on exact release SHA;
- checksum/provenance artifacts;
- technical + factor + ML fixture research examples pass;
- no open release-blocking P0;
- GitHub Release exists and references the exact tag/commit.

---

# 12. Definition of “institutional-grade” for this repository

The term should be reserved until the platform satisfies all of the following categories.

## Data integrity

- survivorship-safe instrument universe;
- PIT financial availability;
- corporate-action correct price basis;
- historical market state / price bands / suspension;
- immutable versioned snapshots;
- dataset quality gates and reconciliation.

## Research integrity

- explicit train/validation/OOS protocol;
- leakage tests;
- transaction-cost and execution realism;
- robustness and multiple-testing controls;
- deterministic experiment provenance.

## Engine correctness

- typed execution contract;
- deterministic order/fill/accounting semantics;
- Backtrader capability boundaries explicitly known;
- parity fixtures across relevant engines/simulation paths.

## Governance

- strategy-version evidence;
- admission gates;
- auditable promotion path;
- immutable reports/artifacts;
- reproducible release artifacts.

## Operations

- configuration/auth/readiness/observability gates;
- recoverable job/data workflows;
- broker-specific certification before live claims;
- rollback and incident procedures.

The platform already has meaningful foundations in each area. The roadmap above is mainly about **closing correctness and evidence gaps**, not restarting the architecture.

---

# 13. Issues created by this audit

| Priority | Issue | Purpose |
|---|---|---|
| P0 | #59 | release/version/tag provenance + stable release gate |
| P0 | #60 | TuShare qfq/hfq correctness + provider conformance |
| P0 | #61 | PIT fundamentals + announcement-date leakage |
| P0 | #62 | T+1 and board/date-specific A-share market rules |
| P1 | #63 | real Backtrader backend + capability/parity contract |
| P1 | #64 | PIT TuShare A-share research data domain |
| P1 | #65 | leakage-safe research validation/OOS/robustness protocol |
| P1 | #66 | V6 runtime ownership / dependency inversion convergence |
| P2 | #67 | evidence-backed docs + TuShare clean-room guide |
| P1 | #68 | experiment/run/strategy-admission evidence lineage |

Recommended implementation order:

```text
#60 + #61 + #62
        ↓
#59 RC release mechanics
        ↓
#63 + #64
        ↓
#65 + #68
        ↓
#66
        ↓
#67 + #59 stable release
```

Some work can run in parallel, but **#60/#61/#62 are correctness gates and must not be hidden by broader architecture work**.

---

## References used in this audit

### Backtrader

- https://www.backtrader.com/docu/cerebro/
- https://www.backtrader.com/docu/data-multitimeframe/data-multitimeframe/
- https://www.backtrader.com/docu/data-resampling/data-resampling/
- https://www.backtrader.com/docu/data-replay/data-replay/
- https://www.backtrader.com/docu/order/
- https://www.backtrader.com/docu/live/live/

### TuShare Pro

- https://tushare.pro/document/2?doc_id=109 — adjusted bars (`pro_bar`)
- https://tushare.pro/document/2?doc_id=28 — adjustment factors
- https://tushare.pro/document/2?doc_id=32 — `daily_basic`
- https://tushare.pro/document/2?doc_id=183 — `stk_limit`
- https://tushare.pro/document/2?doc_id=214 — `suspend_d`
- https://tushare.pro/document/2?doc_id=96 — `index_weight`

### Exchange trading rules

- https://english.sse.com.cn/start/trading/mechanism/
- https://investor.szse.cn/knowledge/stock/chinext/t20200729_580056.html
- https://www.bse.cn/jygl_list/200028217.html
