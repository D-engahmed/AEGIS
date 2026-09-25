# AEGIS Product Roadmap

Status: **active**. Phase 0 (architecture freeze) and Phase 1 run-ownership enforcement are complete.

Current execution: **Phase 2 — Real tracing**.
PR-02 is the durable-tracing increment: PostgreSQL-backed preserved traces, restart-proof trace reads,
run-scoped authorization on trace/cost endpoints, and alignment between score evidence and the persisted
AEGIS trace identifier. The phase remains open until trace ingestion, retrieval, metadata, and failure
semantics are fully proven.

This document
defines the product phases through production beta.

`docs/architecture/architecture-freeze.md` pins the nine architectural
decisions that stay fixed until a recorded decision revokes them. Everything
below happens **inside** the existing boundaries. No folder restructuring, no
new frameworks, no microservices, no Kafka, no Kubernetes, no Terraform, no
OTel SDK adoption, no object storage just because it sounds more
production-grade. Build the missing intelligence.

Reference chain:
`docs/implementation/implementation-order.md` → build-phase dependency
rules, SDK positioning, and the schema-change / API-change protocols
that govern every commit below.

---

## North-star workflow

The target is not "AEGIS has N evaluators." The target is:

```text
A developer changes an AI application, submits it to AEGIS,
AEGIS executes the same evaluation dataset against the old and new versions,
identifies regressions,
traces the failures to the underlying LLM / RAG / tool behavior,
produces evidence-backed analysis,
and blocks the deployment when policy is violated.
```

When AEGIS can reliably do that, it fits the ANCIENT strategy
(ANCIENT builds/runs the AI system → AEGIS independently
measures/verifies it) and is substantially more valuable than an
evaluation dashboard.

---

## v0.1 as-built status

```text
        AEGIS v0.1
             │
             ▼
 ┌──────────────────────┐
 │ Evaluation Runtime   │  ← strong
 ├──────────────────────┤
 │ Evidence             │  ← strong foundation
 ├──────────────────────┤
 │ Deterministic evals  │  ← real
 ├──────────────────────┤
 │ Gates                │  ← real
 ├──────────────────────┤
 │ API / CLI            │  ← real
 ├──────────────────────┤
 │ Tracing              │  ← incomplete
 ├──────────────────────┤
 │ Agent eval           │  ← incomplete
 ├──────────────────────┤
 │ RAG eval             │  ← incomplete
 ├──────────────────────┤
 │ Regression           │  ← foundation / incomplete
 ├──────────────────────┤
 │ Root cause           │  ← incomplete
 ├──────────────────────┤
 │ CI release control   │  ← incomplete
 └──────────────────────┘
```

Do not add more architecture. Build the missing intelligence.

---

## Execution order (authoritative sequence)

Do not start phase N until phase N-1 exit criteria pass.
Exit criteria are verified by tests and documentation, not by assertion.

| # | Phase | Dependency |
|---|---|---|
| 1 | Architecture freeze | (done) |
| 2 | Multi-tenancy + authorization | 1 |
| 3 | Real tracing | 2 |
| 4 | Agent evaluation | 3 |
| 5 | RAG evaluation | 4 |
| 6 | Evaluator plugin boundary | 4, 5 |
| 7 | Regression engine | 3, 4, 5 |
| 8 | Root-cause analysis | 7 |
| 9 | Policy / release gates | 8 |
| 10 | CI/CD integration | 9 |
| 11 | Reports | 3, 8, 9 |
| 12 | Dashboard | 11 |
| 13 | SDK | 11 |
| 14 | Webhooks | 10 |
| 15 | Security hardening | 2, 10 |
| 16 | Production beta | all |

---

## Phase 0 — Architecture freeze ✅

### Goal

Stop architectural churn.

### What was frozen

1. Modular-monolith decision (ADR-001).
2. Layer / dependency direction (`frontend → API → application → domain →
   ports → infrastructure`).
3. PostgreSQL as system-of-record.
4. Redis as execution queue.
5. Worker architecture.
6. Evidence invariant — no score without evidence; immutable history.
7. Evaluator contract — deterministic in-process; RPC boundary unconditionally
   required before any judge-category evaluator.
8. API until a real product requirement forces change (OpenAPI snapshot is
   the contract).
9. Stop creating new architecture documents unless resolving an actual
   implementation decision.

### Exit criterion (achieved)

> Architecture is stable enough that new work happens inside the existing
> boundaries.

### Reference

`docs/architecture/architecture-freeze.md`

---

## Phase 1 — Multi-tenancy and authorization

### Goal

A customer must never see another customer's datasets, targets, prompts,
traces, evaluation results, reports, evidence, API keys, or experiments.

### Scope

#### Commit 1: run-ownership enforcement

- Enforce `run.organization_id == actor.org` on every run-scoped API read
  and mutation (status, cancel, results, evidence, analysis).
- Add cross-tenant negative tests proving a forged or mismatched org
  cannot reach another tenant's run, results, or evidence.

#### Subsequent commits

- [ ] Organization identity backed by persistent tenant records
- [ ] Project membership management (invite, roles, remove)
- [ ] Role-based resource authorization on every endpoint
- [ ] Organization-scoped repository queries
- [ ] Project-scoped repository queries
- [ ] Cross-tenant negative test suite (comprehensive)
- [ ] API authorization middleware / dependencies (replace synthetic tenant
      construction from token)
- [ ] Deletion policy (soft / hard, domain-driven)
- [ ] Retention policy
- [ ] Immutable audit events for every authorization-relevant action
- [ ] PostgreSQL row-level security as a backstop (application-level
      isolation verified first)

### Key principle

RLS is not the authorization model. Application-level tenant isolation is
the security architecture; RLS is the backstop added **after** it is proven
correct.

### Reference

- `docs/architecture/security-architecture.md`
- `docs/development/layers/11-security-layer.md`
- `src/aegis/security/rbac.py`

---

## Phase 2 — Real tracing

### Goal

Make AEGIS understand an actual AI execution: every call, every token,
every tool invocation, every latency measurement.

### Trace model

```text
Run
 ├── LLM call
 │    ├── model
 │    ├── input tokens
 │    ├── output tokens
 │    ├── latency
 │    └── cost
 │
 ├── Retrieval
 │    ├── query
 │    ├── documents
 │    └── relevance
 │
 ├── Tool call
 │    ├── tool
 │    ├── arguments
 │    ├── result
 │    └── latency
 │
 ├── Guardrail
 │
 └── Final answer
```

### Scope

- [ ] Trace domain model (parent/child, span types, execution correlation)
- [ ] Span persistence
- [ ] Trace retrieval API
- [ ] Trace → result relationship
- [ ] Trace → evidence relationship
- [ ] Model metadata, token usage, latency, cost per call
- [ ] Tool metadata
- [ ] Retrieval metadata
- [ ] Error metadata

### Critical invariant

```text
No evaluation result
        ↓
without execution
        ↓
without trace/evidence
```

### Reference

- `docs/architecture/evidence-architecture.md`
- `docs/architecture/architecture-decision-records/ADR-005-trace-storage-strategy.md`

---

## Phase 3 — Agent evaluation

### Goal

Evaluate agent behavior, not just final output quality.

### Evaluators

#### Tool selection

- [ ] Correct tool selected?
- [ ] Unnecessary tools called?
- [ ] Required tool missed?
- [ ] Tool-call precision / recall

#### Arguments

- [ ] Schema correctness
- [ ] Semantic correctness
- [ ] Unsafe argument detection

#### Execution

- [ ] Tool success rate
- [ ] Tool failure recovery
- [ ] Retry behavior
- [ ] Loop detection
- [ ] Unnecessary repetition
- [ ] Step count

#### Planning

- [ ] Goal completion
- [ ] Intermediate-state correctness
- [ ] Premature termination
- [ ] Recovery quality

#### Budget

- [ ] Token budget
- [ ] Latency budget
- [ ] Tool-call budget
- [ ] Cost budget
- [ ] Step budget

### Reference

- `src/aegis/evaluation/plugins.py`
- `src/aegis/evaluation/trajectory.py`

---

## Phase 4 — RAG evaluation

### Goal

AEGIS answers not just "the answer was wrong" but
**"the answer was wrong because retrieval failed, not because generation
failed."** That distinction is the product.

### Retrieval metrics

- [ ] Recall@K
- [ ] Precision@K
- [ ] MRR
- [ ] NDCG
- [ ] Context relevance
- [ ] Context coverage
- [ ] Duplicate retrieval detection
- [ ] Irrelevant retrieval detection

### Generation metrics

- [ ] Answer correctness
- [ ] Groundedness
- [ ] Citation correctness
- [ ] Hallucination detection
- [ ] Answer completeness

### Pipeline diagnosis

- [ ] Retrieval failure vs. generation failure isolation
- [ ] Evidence-backed diagnosis explanations

---

## Phase 5 — Evaluator plugin boundary

### Goal

The current deterministic evaluator registry becomes a proper extensibility
boundary with isolation, versioning, and contracts.

### Evaluator interface

```text
Evaluator
 ├── metadata()
 ├── validate()
 └── evaluate()
```

### Evaluator metadata

```text
id, name, version, type, configuration,
input contract, output contract, dependencies, determinism
```

### Scope

- [ ] Evaluator registry with typed metadata
- [ ] Evaluator versioning (semantic versioning)
- [ ] Evaluator configuration (typed, validated)
- [ ] Evaluator contract tests
- [ ] Evaluator timeout
- [ ] Evaluator failure isolation (deterministic → semantic → LLM judge)
- [ ] Evaluator resource limits
- [ ] Evaluator provenance (who wrote it, what it depends on)
- [ ] Evaluator result schema

### Ordering

```text
Deterministic Evaluators (shipped)
        ↓
Semantic Evaluators (phase 6: this phase's first use)
        ↓
LLM Judge (phase 6: only after isolation boundary proven)
```

Do **not** start with LLM judges. Make the runtime extremely reliable first.

### Reference

- `docs/architecture/architecture-decision-records/ADR-004-evaluator-plugin-isolation.md`

---

## Phase 6 — LLM judge

### Goal

Probabilistic evaluation with a judge model, fully isolated, fully
traceable.

### Judge output

```text
judge_model, judge_model_version, judge_prompt_version,
evaluator_version, score, confidence,
reason/category, evidence, timestamp
```

### Key invariant

```text
judge prompt changes
        ↓
new evaluator version
```

Never silently reinterpret historical scores.

### Scope

- [ ] LLM judge evaluator category (first probabilistic evaluator)
- [ ] RPC / process isolation boundary (ADR-004 requirement)
- [ ] Judge prompt versioning
- [ ] Score + confidence + evidence in judge result
- [ ] Judge prompt change → new evaluator version
- [ ] Historical score immutability guarantee

### Reference

- `docs/architecture/architecture-decision-records/ADR-004-evaluator-plugin-isolation.md`
- `docs/architecture/architecture-migration-plan.md` §V5 evaluator doc

---

## Phase 7 — Regression engine

### Goal

AEGIS answers: **"Did the new version make the AI system worse?"** — not
just "what score did it get?"

### Model

```text
Experiment A
      │
      ├── baseline
      │
      └── candidate
             │
             ▼
        Comparison Engine
             │
       ┌─────┴─────┐
       ▼           ▼
    improved     degraded
```

### Scope

- [ ] Baseline experiment
- [ ] Candidate experiment
- [ ] Test-case alignment across versions
- [ ] Metric comparison
- [ ] Absolute delta
- [ ] Relative delta
- [ ] Regression threshold
- [ ] Improvement threshold
- [ ] Per-test regression
- [ ] Aggregate regression
- [ ] Regression classification (improved / degraded / stable)
- [ ] Statistical significance (Welch's t-test, already partially in
      `src/aegis/analysis/`)
- [ ] Confidence interval
- [ ] Flaky-test detection

### Reference

- `src/aegis/analysis/` (existing trend / regression modules)

---

## Phase 8 — Root-cause analysis

### Goal

Don't stop at:

```text
Quality: 91% → 87%
```

Produce:

```text
QUALITY REGRESSION

Overall: -4.0%

Primary suspected causes:

1. Retrieval recall
   -8.2%

2. Tool selection
   -5.7%

3. Latency
   +1.3s

Affected: 43 / 500 test cases
Most affected slice: financial-support
Common failure: missing customer-account retrieval
```

### Scope

- [ ] Failure clustering
- [ ] Failure fingerprints
- [ ] Slice analysis (by dataset label, target version, evaluator)
- [ ] Dataset-label analysis
- [ ] Target-version comparison
- [ ] Evaluator comparison
- [ ] Trace correlation
- [ ] Root-cause candidates
- [ ] Evidence-backed explanations

### Reference

- `src/aegis/analysis/` (failure classification, trend analysis)

---

## Phase 9 — Policy / release gates

### Goal

Make basic PASS/WARN/BLOCK gates production-grade and auditable.

### Gate definition model

```yaml
gate:
  quality:
    minimum: 0.90
  safety:
    critical_failures: 0
  latency:
    p95:
      maximum_ms: 3000
  cost:
    maximum_per_run: 0.05
  regression:
    maximum_delta: -0.02
```

### Execution

```text
Evaluation
    ↓
Analysis
    ↓
Policy Engine
    ↓
PASS / WARN / BLOCK
```

### Scope

- [ ] Composite conditions (AND / OR / NOT)
- [ ] Severity levels
- [ ] Non-compensatory safety dimensions
- [ ] Threshold versioning
- [ ] Gate versioning
- [ ] Gate evidence (immutable, appended)
- [ ] Authorized override (actor, reason, timestamp, immutable audit)

### Reference

- `src/aegis/application/run_gates.py`
- `src/aegis/policy/` (existing gate logic)

---

## Phase 10 — CI/CD integration

### Goal

AEGIS becomes a real gate in the engineering workflow.

### Model

```text
Git Push
   ↓
Build
   ↓
Deploy candidate
   ↓
AEGIS evaluation
   ↓
Regression analysis
   ↓
Policy
   ↓
PASS ─────→ Production
BLOCK ────→ Deployment stopped
```

### Scope

- [ ] GitHub Actions integration
- [ ] Generic CI API (not GitHub-specific at the application layer)
- [ ] Evaluation trigger (programmatic, not dashboard-only)
- [ ] Polling / webhook-based completion
- [ ] Gate result → deployment exit code
- [ ] PR comment / report link
- [ ] Baseline selection
- [ ] Candidate selection
- [ ] Artifact / report link
- [ ] Failed deployment evidence

---

## Phase 11 — Reports

### Goal

Every number in a report should be traceable to its source.

```text
Report
 ↓
Analysis
 ↓
Result
 ↓
Execution
 ↓
Trace
 ↓
Evidence
```

### Report structure

```text
AEGIS Evaluation Report

 1. Executive Summary
 2. System Under Test
 3. Experiment Configuration
 4. Dataset
 5. Evaluation Metrics
 6. Baseline vs Candidate
 7. Regressions
 8. Failures
 9. Agent Trajectories
10. RAG Analysis
11. Cost & Latency
12. Policy Verdict
13. Evidence
14. Reproducibility Metadata
```

### Reference

- `src/aegis/analysis/` (existing report data structures)

---

## Phase 12 — Dashboard

### Goal

Build screens around **workflows**, not entities.

### Screens

#### Overview

```text
AI Systems / Experiments / Runs
Pass Rate / Regressions / Critical Failures
Cost / Latency
```

#### Experiment detail

```text
Baseline / Candidate
Metrics / Regression / Failures / Evidence
```

#### Run detail

```text
Status / Timeline / Trace
Tool Calls / Retrieval / LLM Calls
Costs / Errors
```

#### Regression detail

```text
What changed? / Where? / How much? / Why?
Evidence
```

#### Gate detail

```text
PASS / WARN / BLOCK
Reason / Evidence / Policy / Override
```

### Reference

- `frontend/` (existing static dashboard boundary)
- `docs/architecture/container-architecture.md` (separate static deployable)

---

## Phase 13 — SDK

### Goal

The SDK surfaces the stable product contract, not an internal
implementation detail. Build it after the report contract (Phase 11)
is stable.

### Scope

- [ ] Python SDK
- [ ] Authentication
- [ ] Organizations / Projects / Targets / Datasets
- [ ] Experiments / Runs / Results
- [ ] Traces
- [ ] Reports
- [ ] Gates
- [ ] Typed models
- [ ] API versioning support
- [ ] Retry behavior
- [ ] Idempotency

### Reference

- `docs/implementation/implementation-order.md` §Position of the SDK

---

## Phase 14 — Webhooks

### Goal

Push-based notifications for asynchronous workflows.

### Events

```text
run.completed / run.failed / run.cancelled
evaluation.completed
gate.passed / gate.warned / gate.blocked
```

### Scope

- [ ] Signed payload
- [ ] Event ID + timestamp
- [ ] Schema version
- [ ] Idempotency (duplicate delivery rejection)
- [ ] Retry + exponential backoff
- [ ] Delivery history
- [ ] Dead-letter handling

### Reference

- `docs/api/webhooks.md` (planned-but-not-implemented, already documented)

---

## Phase 15 — Security hardening

### Scope

The architecture migration audit explicitly identified gaps that must not be
ignored simply because the architecture is clean:

- [ ] Remove / lock `AEGIS_DEV_LOGIN` in production (never accept
      environment-variable auth)
- [ ] Move auth secret to environment / secret manager (no hard-coded secret)
- [ ] Proper tenant lookup (no synthetic organizations constructed from
      tokens — organizations persisted and verified)
- [ ] Proper user identity (OAuth2 / OIDC integration)
- [ ] RBAC enforcement tests (every role × every endpoint)
- [ ] Authorization failure audit logging
- [ ] PII redaction in logs and traces
- [ ] Secret scanning in CI
- [ ] Dependency scanning in CI
- [ ] SAST in CI
- [ ] Container scanning in CI
- [ ] Coverage threshold
- [ ] Security CI gate

### Reference

- `docs/development/layers/11-security-layer.md`
- `src/aegis/security/` (auth, rbac, audit, pii modules)

---

## Phase 16 — Production beta

### Exit criterion

All previous phases are passing their own exit criteria and the north-star
workflow runs end-to-end in a production-like environment:

```text
Developer commits
  → AEGIS evaluates old + new versions
  → Regressions identified
  → Root cause traced
  → Evidence-backed analysis produced
  → Policy gate verdicted
  → Deployment gated or passed
```

---

## Next commits (immediate, by phase 2)

### Commit 1 — `feat: enforce tenant isolation on run-scoped reads` ✅ (`8f53bf1`)

- [x] Load run, verify `run.organization_id == actor.org` before returning
      results, evidence, or analysis.
- [x] Cross-tenant negative tests proving a run in org B returns 404 when
      requested by org A (and a foreign cancel does not mutate the run).
- [ ] Persist organizations instead of synthesizing them from the token
      (subsequent commit)

### Subsequent commits

- `feat: persist organizations and replace synthetic tenant construction`
- `feat: add project-scoped repository queries`
- `feat: add comprehensive cross-tenant negative test suite`
- `feat: add API authorization dependency for every protected endpoint`

---

## Constraints that do not change

- **No microservices.** ADR-001 is in force.
- **No new external dependencies** without the procedure in
  `docs/development/dependency-rules.md`.
- **No API change** without the protocol in
  `docs/implementation/api-change-protocol.md`.
- **No schema change** without a versioned migration per
  `docs/implementation/database-change-protocol.md`.
- **No new architecture documents** unless resolving an actual implementation
  decision.
- **Domain is stdlib-only.** `scripts/check_domain_purity.py` runs in CI.
- **Dependency direction is strict.** `scripts/check_layer_boundaries.py`
  runs in CI.