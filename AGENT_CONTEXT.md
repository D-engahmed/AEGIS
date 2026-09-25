# AEGIS Engineering Context

Living handoff artifact for the AEGIS product. Update it whenever the execution phase, active PR, architecture constraint, or verified state changes. It exists so an engineering agent can resume from repository truth instead of chat memory.

## Product

AEGIS is the independent AI Evaluation, Reliability & Observability Platform paired with ANCIENT.
ANCIENT builds/runs AI systems. AEGIS measures/verifies them.

North-star workflow:
1. A developer changes an AI application.
2. AEGIS runs the same immutable evaluation dataset against the old and new versions.
3. AEGIS observes LLM, retrieval, tool, guardrail, and final-answer behaviour.
4. AEGIS produces evidence-backed metrics and diagnosis.
5. Policy gates determine whether the change can ship.
6. Reports, API, CLI, SDK, dashboard, webhooks, and CI expose the decision without bypassing evidence.

## Non-negotiable invariants

- No score without evidence.
- Historical results, locked datasets, published target/evaluator versions, and executed experiment snapshots are immutable/write-once.
- A foreign tenant is indistinguishable from a missing tenant-owned resource at the HTTP boundary.
- Evaluation traces are never sampled away.
- Deterministic evaluators come before risk-bearing LLM judges.
- Any judge evaluator requires the isolated evaluator boundary from ADR-004 before implementation.
- PostgreSQL is the source of truth; Redis is the execution queue.
- AEGIS stays a modular monolith until an accepted ADR proves a deployment boundary is required.
- Domain purity and layer-direction checks are mechanical CI gates.

## Frozen architecture references

Read these before changing boundaries:
- docs/architecture/architecture-freeze.md
- docs/architecture/high-level-architecture.md
- docs/architecture/system-context.md
- docs/architecture/component-architecture.md
- docs/architecture/evidence-architecture.md
- docs/architecture/security-architecture.md
- docs/architecture/architecture-decision-records/

Do not invent a new architecture in an implementation PR. Change a frozen decision only through an accepted ADR.

## Repository baseline

- Repository: D-engahmed/AEGIS
- Main baseline before PR-02: 654364e838d55af5014252ed86cff9d862fdf0fe
- PR-01 is merged: expanded deterministic agent trajectory evaluation (tool precision, recall, loop detection, recovery fraction, step-budget validation).
- Phase-1 run ownership enforcement was merged at commit 8f53bf1c5935f36bcd6ae2416a802018b0d64c52 and is in the current main history.
- Product code is a Python 3.12 modular monolith with FastAPI, PostgreSQL, Redis, a worker, CLI, SDK, static dashboard, and layered tests.
- Repository shape observed before PR-02: 343 tracked tree entries, 128 Python source files, 119 docs, 72 test files.

## Reality audit

The docs currently describe more CI capability than the workflow actually implements. docs/ci-cd/* describes selective integration, sharding, security scanning, coverage-diff enforcement, artifacts, and reproducibility controls; .github/workflows/ci.yml currently runs lint/format/mypy/purity/layer checks/docs validation/unit+coverage/contract plus one full integration job. Treat implementation as source of truth until a PR closes each gap.

deploy.yml is currently manual (workflow_dispatch) even though older README prose describes automatic main-branch deployment. Verify deployment claims before calling production-ready.

The current observability implementation has an in-memory preservation layer and an OTLP HTTP exporter. OTLP export is not the same thing as durable AEGIS evidence storage; PostgreSQL persistence is required for restart-proof evaluation analysis.

## Active execution state

### Phase 2 — Real tracing

PR-02 branch: feat/phase-2-trace-persistence

PR-02 scope:
- Add an application-level portable trace payload/store contract without coupling the port to OTel.
- Persist preserved evaluation traces to PostgreSQL with write-once semantics.
- Keep a memory adapter for unit/local operation.
- Make the existing trace read API restart-proof.
- Close run-scoped authorization on /observability/cost/{run_id} and /observability/traces/{run_id}.
- Align MetricResult evidence trace_artifact_id with the AEGIS evaluation trace id whenever tracing is configured.
- Add integration proof that a new Container instance sees the same trace and evidence link.

PR-02 is not the end of Phase 2. Remaining Phase-2 work includes richer span metadata, retrieval semantics, trace/result/evidence graph linkage beyond the current reference, ingestion hardening, and failure-mode coverage.

## Ordered product PR roadmap

Use one vertical capability per PR. Every PR must have: requirement, design delta, implementation, focused unit tests, required integration/contract tests, review of failure modes, docs update, CI evidence, and explicit exit criteria.

| PR | Capability | Exit condition |
|---|---|---|
| 01 | Agent trajectory evaluators | merged; deterministic trajectory metrics proven |
| 02 | Durable trace persistence | restart-proof traces + evidence trace-id alignment + tenant isolation |
| 03 | Trace completeness | model/tool/retrieval/error/token/latency/cost metadata proven end-to-end |
| 04 | Agent semantics | argument correctness, retry quality, loops, planning, budget dimensions with explicit configs |
| 05 | RAG evaluation | retrieval metrics + groundedness/citation/completeness + retrieval-vs-generation diagnosis |
| 06 | Evaluator isolation boundary | process/RPC sandbox exists before any judge-category evaluator |
| 07 | Regression engine | paired baseline/current comparisons, minimum sample policy, significance + practical delta, reproducible reports |
| 08 | Root-cause analysis | failure slicing links regressions to trace spans/retrieval/tool/model causes |
| 09 | Release policy engine | multi-gate, non-compensatory verdicts, evidence-backed override trail |
| 10 | CI/CD control plane | PR/release evaluation, coverage/security/contract/migration gates actually implemented |
| 11 | Reports | machine-readable + human-readable reports with provenance and release verdict |
| 12 | Dashboard | real API-backed evaluation workspace, regression/trace/evidence drill-down |
| 13 | SDK | stable Python client maintained from the API contract; no hidden alternate protocol |
| 14 | Webhooks | signed, idempotent, replay-safe release/evaluation events |
| 15 | Security hardening | persistent org identity, full endpoint RBAC, audit persistence, retention/deletion, RLS backstop |
| 16 | Production beta | SLOs, backup/restore, upgrade/rollback drill, security review, release evidence, operator runbooks |

## Dependency order

01 → 02 → 03 → 04 → 05 → 06 → 07 → 08 → 09 → 10 → 11 → 12 → 13 → 14 → 15 → 16

A downstream feature cannot be declared complete because its code exists; its upstream evidence path must already be real.

## Engineering workflow for every PR

1. Discover: read authoritative docs and current code; identify the invariant/user requirement; search for existing implementations first.
2. Pressure-test: retries, restart, forged IDs, missing evidence, rollback, determinism, API/database contracts, duplicate sources of truth, and false-green CI.
3. Implement the smallest correct vertical slice.
4. Test: focused unit, contract, integration, authorization negative tests, migration tests, and a regression test for the motivating bug.
5. Review the diff as a hostile reviewer: bypass paths, mutability, retry/timeout bounds, idempotency, tenant leaks, global state, N+1 access, nondeterministic scoring, stale docs.
6. Run the repository gates; record what actually ran.
7. Merge only when the PR exit criteria are evidenced.

## Current gate policy

The intended merge gates are documented in docs/ci-cd/pull-request-gates.md and include formatting, typing, unit tests, migrations, API contracts, security, coverage-diff, architecture boundaries, and required documentation. The implementation gap in .github/workflows/ci.yml is an explicit future product-engineering task, not a reason to claim the gates already exist.

## Handoff record

CURRENT PR: PR-02 — https://github.com/D-engahmed/AEGIS/pull/2
BRANCH: feat/phase-2-trace-persistence
BASE COMMIT: 654364e838d55af5014252ed86cff9d862fdf0fe
CURRENT HEAD: 63764126d8c909f64763587545543b301142fa27
WHAT CHANGED: durable trace store contract, PostgreSQL trace persistence, memory trace adapter, storage-backed preservation, trace-id alignment in execution evidence, run-scoped observability authorization, schema migration, focused/integration tests, roadmap state
WHAT WAS VERIFIED: source-level review, Ruff line-length scan, layer-boundary review, PR creation, and branch comparison
WHAT FAILED: GitHub Actions has not reported a workflow run/status for the branch; this GitHub session has no local runtime for pytest/ruff/mypy
OPEN RISKS: verify migration 3 against a real existing schema; verify JSON round-trip for all span attribute types; ensure trace persistence failure cannot leave a successful run without its intended trace evidence; verify the exact trace/evidence relationship under failed/retried runs; inspect deployment workflow before production claims
NEXT PR: PR-03
NEXT FIRST ACTION: run PR-02 CI and fix every failure before merge; then expand trace completeness rather than adding unrelated architecture

## Definition of done

A feature is not complete when the code compiles. It is complete when requirements map to code, the correct layer owns the behaviour, state survives required failure boundaries, security boundaries are tested negatively, contracts are stable/versioned, migrations are safe, observability explains outcomes, evidence can reproduce claims, CI verifies the same assumptions developers use locally, docs match deployment reality, and the next engineer/agent can resume from this file.
