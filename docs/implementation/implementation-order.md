# Implementation Order

This document is the recommended build order for AEGIS. It turns the phase plan in `README.md` and the MVP guidance and product facts in `grilling.md` into concrete phases, each with a goal, a scope, deliverables, tests, and exit criteria. A phase is not "started when the features sound ready"; it is started when the previous phase's exit criteria pass. The order exists to protect the evidence chain: you cannot evaluate an experiment before you have immutable datasets, targets, and experiments; you cannot analyze results before results have evidence; you cannot build an SDK on top of a contract that does not exist yet.

## The Ordering Rule

```text
Do not start phase N until phase N-1 exit criteria pass.

Exit criteria are verified by tests and documentation, not by assertion.
```

The gates are enforced the same way any other gate in AEGIS is enforced: a phase is considered complete when its exit criteria are demonstrated in the local and CI environments (`docs/testing/test-environments.md`, `docs/ci-cd/pull-request-gates.md`) and its acceptance criteria are met (`docs/requirements/acceptance-criteria.md`). A skipped or partially completed phase corrupts everything built on top of it, because later phases assume earlier phase invariants hold. The order below is mandatory ordering of dependencies, not a suggestion about scheduling.

## Position of the SDK

`README.md` is explicit:

```text
Do not start with the SDK.
First build: REST Target + Evaluation Engine + Experiment System.
```

The SDK is Phase 5. An SDK is a consumer of the API and of the evaluation/experiment model; building it before the REST target adapter, the evaluation engine, and the experiment system exist means building a client for an interface that has not been defined or exercised. The REST target adapter defined in Phase 2 is what teaches the platform how to invoke an AI system; the evaluation engine and the experiment system are what make that invocation meaningful. The SDK can only be designed against the contract those three systems establish.

---

## Phase 0 — Project Scaffolding

### Goal

Stand up the repository, the layered structure, the module boundaries, and the CI skeleton so that every later phase has a tested home.

### Scope

- Repository layout and tooling per `docs/development/layers/` (layers 00-11) and `docs/development/coding-standards.md`.
- Modular monolith structure per ADR-001.
- CI skeleton: lint, typecheck, unit test harness, and the per-PR gate set (`docs/ci-cd/pull-request-gates.md`).
- Local test harness capable of running unit and fast integration tests with contained PostgreSQL and Redis (`docs/testing/test-environments.md`).

### Deliverables

- Layered repository structure with dependency rules enforced (`docs/development/dependency-rules.md`).
- CI pipeline that runs and passes on every change.
- Empty-but-documented module skeletons for the Control Plane, Execution Plane, and Evidence Plane.

### Exit Criteria

- CI runs and passes on a no-op change.
- Local unit-test harness runs without a real provider (fixtures only).
- Dependency rules are mechanically checked (no forbidden imports).
- Layer documentation exists for every layer that will receive code (`docs/development/layers/`).

### Defining Documents

`README.md` §16 (MVP architecture), `docs/development/`, ADR-001.

---

## Phase 1 — Identity, Tenancy, and the Control Plane Foundation

### Goal

Establish the entities everything else references: organizations, projects, targets, target versions, datasets, and test cases, including the immutability rules that make evaluation results trustworthy.

### Scope

- Identity and tenancy: organizations, projects, roles, and tenant ownership of every persistent object (`docs/architecture/security-architecture.md`, grilling.md Q76-Q100).
- Projects, targets, and immutable target versions.
- Datasets and test cases, with the draft/lock lifecycle.
- **Lock/immutability** enforcement: a locked dataset version cannot be modified or deleted; a target version referenced by an experiment cannot be changed (grilling.md Q45-Q46, Q52-Q55; `docs/data/immutability-rules.md`; `docs/architecture/write-architecture.md`).
- The schema, ER model, and migrations for the above (`docs/data/database-design.md`, `docs/data/er-diagram.md`).

### Deliverables

- Working API for projects, targets, target versions, datasets, test cases, and lock operations.
- Write invariants enforced at the application layer and, where possible, at the database layer.
- Migrations for the Phase 1 schema, passing the CI migration gates.

### Exit Criteria

- A dataset version, once locked, rejects all update and delete attempts.
- A target version, once referenced, rejects all update and delete attempts.
- Every tenant-owned record carries `organization_id` / `project_id`, and cross-tenant access tests fail correctly.
- Migration tests and integration tests for immutability pass in CI (`docs/data/schema-evolution.md`, `docs/testing/integration-testing.md`).

### Defining Documents

`README.md` §4-§5, §15 (domain entities, tenancy), `docs/architecture/write-architecture.md`, `docs/data/immutability-rules.md`, `docs/data/schema-evolution.md`, `docs/requirements/functional-requirements.md`.

---

## Phase 2 — Experiments, Execution, and Deterministic Evaluation

### Goal

Make evaluation real: define experiments against immutable snapshots, execute them asynchronously against targets, and produce the first deterministic results with full evidence wiring.

### Scope

- Experiments: reproducible configuration snapshots, clone-for-comparison, immutability after execution begins (grilling.md Q151-Q175).
- Async execution: queue, worker pool, bounded retries with exponential backoff and error classification, mandatory timeouts, cooperative cancellation (grilling.md Q176-Q200; `docs/architecture/execution-architecture.md`; ADR-002).
- **REST target adapter**: the first integration mode for invoking a target system (`docs/api/async-execution-contract.md`).
- **Deterministic evaluators**: latency, cost, exact match, JSON validation / schema validity (grilling.md Q39, Q204-Q208; `README.md` §8).
- **Results + evidence wiring**: every result references its full upstream chain (execution, trace, evaluator identity and version). "No score without evidence" becomes a testable invariant (`docs/architecture/evidence-architecture.md`, `docs/data/immutability-rules.md`).

### Deliverables

- Asynchronous execution pipeline: experiment -> executions -> metric results with evidence links.
- REST target adapter with a contract-tested invocation envelope and failure mapping to the error taxonomy.
- Deterministic evaluator plugins with results carrying provenance.
- Retry, timeout, cancellation, and idempotency behavior tested, including preservation of partial evidence from failed and cancelled executions.

### Exit Criteria

- An experiment is immutable once execution begins; cloning produces a separate variant.
- End-to-end run of a deterministic evaluation against a REST target produces results with complete evidence references.
- Bounded retry with exponential backoff and error classification is tested; no infinite retry path exists.
- Timeouts and cancellation work; cancelled and failed executions preserve partial evidence and are distinguishable.
- Deterministic evaluator results include evaluator identity and version.

### Defining Documents

`README.md` §3, §7-§8, §12 (orchestrator, workers, metrics), §16 (MVP), `docs/architecture/execution-architecture.md`, `docs/architecture/evidence-architecture.md`, `docs/api/async-execution-contract.md`, ADR-002, ADR-003.

---

## Phase 3 — Tracing, Agent Evaluation, and Sophisticated Evaluators

### Goal

Add the evaluation depth that makes AEGIS effective for agents and RAG: OpenTelemetry-compatible tracing, trajectory-level agent/tool evaluation, semantic and LLM-judge evaluators with confidence and provenance, and isolated evaluator plugins.

### Scope

- **Agent tracing**: OpenTelemetry-compatible span model for model calls, retrieval, tools, memory, guardrails, and agent execution (README.md §6, §9; grilling.md Q451-Q475; ADR-005).
- **Tool/agent evaluation**: tool selection, arguments, result handling, loops, recovery, step budget (grilling.md Q351-Q400).
- **Semantic evaluators**: embedding-based similarity and relevance, as deterministic as the model permits.
- **LLM-judge evaluators**: with confidence, evaluator identity and version, and judge prompt version on every result (grilling.md Q41-Q44, Q226-Q250; `README.md` §8).
- **Evaluator plugin isolation**: evaluators run as plugins behind a stable, contract-tested interface in a separate process or RPC boundary (ADR-004).

### Deliverables

- Trace collection and storage linked to executions (`docs/architecture/evidence-architecture.md`, ADR-005).
- Trajectory evaluation of agents: loop detection, recovery measurement, step count, tool accuracy, budget enforcement (README.md §9; grilling.md §XV, §XVI).
- Semantic and LLM-judge evaluator categories behind the ADR-004 plugin boundary, with versioning of evaluator/judge-prompts.
- `evaluate()`, `validate()`, `metadata()` interface contract tests (`docs/testing/contract-testing.md`).

### Exit Criteria

- A trace from an agent execution links to its test execution and to the resulting metric results.
- LLM-judge results are never produced without confidence, evaluator identity, evaluator version, and judge prompt version.
- Changing the judge model or judge prompt creates a new evaluator version; historical comparisons are not silently re-interpreted.
- A crashing or misbehaving evaluator plugin cannot take down the control plane.
- Evaluator plugin contract tests pass on both sides of the boundary.

### Defining Documents

`README.md` §6, §9 (traces, agent evaluation), `docs/architecture/evidence-architecture.md`, `docs/architecture/execution-architecture.md`, ADR-004, ADR-005, `docs/development/layers/05-execution-layer.md`, `docs/development/layers/06-evaluation-layer.md`.

---

## Phase 4 — Analysis, Reporting, and Policy Gates

### Goal

Turn results into decisions: regression detection, failure classification, slicing, significance, reports, and gates that pass/warn/block with human override.

### Scope

- **Analysis engine**: regression detection, failure classification and clustering, slicing across labels and dataset dimensions, statistical significance (README.md §10-§11; grilling.md §XX).
- **Reports**: reproducible report generation from evidence-backed results.
- **Policy & gates engine**: composite logic, non-compensatory dimensions, pass/warn/block decisions, configurable thresholds (grilling.md Q231-Q244, Q476-Q500; `docs/development/layers/08-policy-and-gates-layer.md`).
- **Overrides**: a blocked gate can be overridden only by authorized actors, and the override is evidence-recorded and auditable (grilling.md Q499).

### Deliverables

- Regression detection over experiment variants (per-test comparison, not only aggregate).
- Failure classification and slicing across dataset labels.
- Gate evaluation with `quality >= 0.90 AND critical_safety_failures == 0 AND p95_latency < 3s` style composite logic.
- Override workflow with authorization and audit trail.

### Exit Criteria

- A regression is detected per test case and is blockable.
- A safety failure cannot be compensated for by a quality improvement (non-compensatory dimensions).
- Gate verdicts and overrides are recorded with the evidence that produced them.
- Flaky metrics are distinguishable from blocking metrics.
- Analysis outputs reference their source results; there is no report claimed without evidence.

### Defining Documents

`README.md` §10-§11, `docs/development/layers/07-analysis-layer.md`, `docs/development/layers/08-policy-and-gates-layer.md`, `docs/architecture/evidence-architecture.md`, `grilling.md` §XX (regression/release gates).

---

## Phase 5 — SDK, Production Readiness, and Hardening

### Goal

Make AEGIS consumable and operationally safe: SDK, production observability, CI/CD integration, webhooks, and multi-tenant hardening. This phase is only reachable after the REST target adapter, the evaluation engine, and the experiment system exist.

### Scope

- **SDK**: a consumer of the Phase 1-4 contracts; tracing facade, experiment/result clients, deprecation surfacing (README.md §14; `grilling.md` "Do not start with the SDK").
- **Production observability**: AEGIS's own telemetry, alerting, and reliability monitoring (`docs/development/layers/10-observability-layer.md`).
- **CI/CD integration**: evaluation gates in deployment pipelines, test tagging, smoke and canary evaluation (grilling.md Q482-Q499).
- **Webhooks**: event delivery with a pinned, contract-tested payload (re-run completed, failed, cancelled, verdict produced) with bounded retries and idempotent delivery (`docs/api/webhooks.md`).
- **Multi-tenant hardening and RLS**: row-level security as defense-in-depth, permission model verified at every boundary, retention and deletion controls verified (grilling.md Q81-Q100; `docs/architecture/security-architecture.md`).

### Deliverables

- SDK released against the versioned API, with contract tests proving consumer compatibility.
- Webhook subsystem with delivery contract tests.
- Deployment gate integration shown end to end (CI -> evaluation -> gate -> deploy or block).
- RLS enabled and tested as a defense-in-depth layer; cross-tenant leakage tests pass at every layer.
- Production observability runbook and alerts.

### Exit Criteria

- SDK contract tests pass against the live API; breaking API changes require the deprecation lifecycle before they reach the SDK.
- Webhook delivery is idempotent, bounded, and verifiable by subscribers.
- A failed evaluation gate blocks a deployment pipeline; an authorized override records evidence and is auditable.
- RLS does not weaken any existing enforcement and cross-tenant tests still fail correctly.
- Production monitoring detects and alerts on degraded reliability without inventing data.

### Defining Documents

`README.md` §14-§15, `docs/api/versioning-policy.md`, `docs/api/webhooks.md`, `docs/architecture/security-architecture.md`, `docs/data/retention-and-deletion.md`, `docs/development/layers/10-observability-layer.md`, `docs/development/layers/11-security-layer.md`, ADR-003.

---

## Phase Ordering Invariants

The following invariants hold across all phases and are derived directly from `grilling.md` and `README.md`:

1. **SDK is last.** The SDK ships only after the REST target adapter, the evaluation engine, and the experiment system exist (`README.md` §14; grilling.md Q65-Q66).
2. **REST target before SDK.** The black-box HTTP integration mode is the first integration mode; the SDK is built to interoperate with it, not before it (`grilling.md` Q65-Q66).
3. **Immutability before evaluation.** Locking and immutability (Phase 1) precede experiments and results (Phase 2), so that no score can ever silently change meaning (grilling.md Q45-Q46).
4. **Evidence before analysis.** Results with full evidence wiring (Phase 2-3) precede regression, reports, and gates (Phase 4), because gate verdicts without evidence are not defensible (grilling.md Q499, "No score without evidence").
5. **Deterministic before probabilistic.** Deterministic evaluators (Phase 2) come before semantic and LLM-judge evaluators (Phase 3), so the platform proves its evaluator contract on mechanical metrics first (grilling.md Q39-Q40).
6. **Never skip a phase for speed.** A phase that is not gated on the previous phase produces software that resembles a dashboard without trustworthy measurements, the single largest product mistake identified in the interrogation (grilling.md Q17).