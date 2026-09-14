# Architecture Freeze (Phase 0)

Status: **in force from the completion of the architecture migration (Phase 1,
`docs/architecture/architecture-migration-plan.md`) until a recorded decision
revokes it.**

Purpose: stop architectural churn. The system below is what AEGIS *is* as
built and verified. The freeze items fix the decisions that would otherwise be
re-litigated; the sections that follow name what "unfreezing" costs, so no
change to a frozen item is ever accidental.

Everything in this document is a restatement of an already-recorded decision
and the as-built code that verifies it. Nothing here is new. Cross-references
are the authority; this document only draws the line.

---

## 1. Freeze the modular-monolith decision

- **What is frozen.** AEGIS is a modular monolith: one Python package
  (`src/aegis/`, layers 01–11), one Docker image, deployed as multiple
  processes from that image. No microservices, no Kafka, no Kubernetes.
  (ADR-001, `docs/architecture/architecture-migration-plan.md` §1, §6.)
- **Evidence.** `src/aegis/` is a single package; `Dockerfile` builds one
  image; `docker-compose.yml` runs two services (`api`, `aegis` worker) from
  that one image.
- **Unfreeze.** An accepted ADR proposing an independent deployment boundary
  for a component, with a revenue- or reliability-justified trigger. The
  architecture audit already found no evidence any such boundary is needed.

## 2. Freeze dependency and layer direction

- **What is frozen.** Dependency direction is strict and one-way:
  `frontend → API (interface) → application → domain → ports →
  infrastructure`. Frontend is a separate static deployable that talks only to
  the FastAPI HTTP surface (no direct database, no direct Redis). Domain code
  is stdlib-only (zero framework imports). No layer may reach across to a
  non-neighboring layer without an ADR.
  (`docs/development/development-rules.md` §Dependency Direction, §Domain
  Purity; `docs/development/dependency-rules.md`; layer files under
  `docs/development/layers/`.)
- **Evidence.** `scripts/check_domain_purity.py` and
  `scripts/check_layer_boundaries.py` run in CI and fail on any violation
  (112 source files checked); mypy fails on port/implementation signature
  drift (21 infrastructure adapters declare port bases).
- **Unfreeze.** An accepted ADR for the specific crossing. None currently
  justified.

## 3. Freeze PostgreSQL as system-of-record

- **What is frozen.** PostgreSQL is the system of record for all persisted
  records (metadata, runs, results, evidence, gate reports). Access is raw
  `psycopg`, no ORM. Schema changes are versioned, rollback-capable DDL
  migrations. (ADR-003; `src/aegis/infrastructure/migrations.py`,
  `aegis_schema_versions` table; `docs/data/schema-evolution.md`.)
- **Evidence.** Compose runs `postgres:17-alpine` (port `5433`); integration
  suite proves records survive restart and are queryable; grep-verified zero
  ORM usage in `src/`.
- **Unfreeze.** An accepted ADR replacing/recomplementing the store, plus the
  standard schema-evolution path (`docs/implementation/database-change-protocol.md`).

## 4. Freeze Redis as execution queue

- **What is frozen.** Redis carries the job queue and is the explicit contract
  between the control plane and the execution workers. No other queue
  technology. At-least-once redelivery with idempotent execution and
  deduplicated evidence linking.
  (ADR-002; `docs/architecture/execution-architecture.md`; compose `redis:7-alpine`,
  port `6380`.)
- **Evidence.** Compose wiring; integration tests prove claim/execute
  redelivery and idempotency.
- **Unfreeze.** An accepted ADR (e.g. durability bounds exceeding Redis's
  guaranteed delivery), with the queue adapter swapped behind the existing
  ports — nothing else in the system may change as a side effect.

## 5. Freeze worker architecture

- **What is frozen.** Execution work is claimed and run by worker processes
  (`aegis worker --watch`) from the same image as the API; the queue is the
  only hand-off. CLI entry points are `version` / `probe` / `record` /
  `evaluate` / `worker` / `serve`. Gate evaluation runs inside the execution
  engine (worker or in-process CLI evaluation) over persisted results; the API
  process never evaluates gates itself — it serves persisted gate reports and
  records authorized overrides.
  (`docker-compose.yml`; `src/aegis/interface/cli.py`; container docs;
  step 7/8 of the migration plan.)
- **Evidence.** Compose `aegis` service runs `worker --watch` with a
  store-aware `probe` healthcheck; the composed worker claims and executes a
  run against a live target and commits run + executions + evidence to
  PostgreSQL.
- **Unfreeze.** An accepted ADR. The worker already runs as an independently
  runnable/scalable process; a *microservice* extraction additionally requires
  §1's unfreeze.

## 6. Freeze the evidence invariant

- **What is frozen.** **No score without evidence** — every score links
  execution → trace → evaluator → evidence. Historical data (dataset versions,
  results, experiment records, evidence) is immutable; write-once. Evidence
  artifacts stay content-hashed in-process (deduplicated by hash) until an
  object-storage adapter ships. Corrections are appended, never rewritten.
  (`docs/architecture/high-level-architecture.md`,
  `docs/architecture/evidence-architecture.md`; `docs/development/development-rules.md`
  §Immutable Historical Data; ADR-005 implementation note.)
- **Evidence.** Contract tests assert every results payload carries evidence
  links; immutable rows are enforced at the storage layer; integration tests
  prove a blocked run's report and override survive a container restart.
- **Unfreeze.** An accepted ADR touching the immutability guarantee or the
  evidence plane boundary — explicitly listed in
  `docs/architecture/README.md` as an ADR-required change.

## 7. Freeze the evaluator contract

- **What is frozen.** Evaluators are deterministic, versioned, and run as an
  in-process plugin registry (`src/aegis/evaluation/plugins.py`,
  `src/aegis/evaluation/trajectory.py`). No third-party evaluator adapters
  (DeepEval, Ragas, etc.) are integrated. The RPC/process isolation boundary
  (ADR-004) must be introduced **before** any LLM-judge or otherwise
  risk-bearing evaluator is added; it is the cost of that category, not an
  auction to be deferred.
  (ADR-004 decision + implementation note.)
- **Evidence.** Plugin registry is the only evaluator execution path; ADR-004
  "When to Revisit"/implementation note records the boundary trigger.
- **Unfreeze.** The trigger is unconditional (see above): adding a judge-class
  evaluator requires the isolation boundary first. Deterministic-only use does
  not unlock boundary removal.

## 8. Freeze the API until a real product requirement forces change

- **What is frozen.** The shipped HTTP API is flat, auth-scoped, unprefixed
  (`POST /runs -> 201`; collections under `/catalog`, `/experiments`,
  `/runs`, `/analysis`, `/policy`, `/evaluators`, `/evidence`,
  `/observability`, `/health`, `/security`). The contract is
  `tests/contract/snapshots/openapi.json`, asserted byte-for-byte by the
  contract suite (27 tests). No new endpoints, signature changes, shape
  changes, or status-code changes without a real product requirement — scope
  creep is a defect.
  (`docs/api/versioning-policy.md` as-built note; `docs/api/api-design.md`
  as-built note; `docs/implementation/api-change-protocol.md`.)
- **Evidence.** Contract tests + snapshot fail on any unintentional API
  drift; the admin/dev-login gate and CORS opt-in are the only HTTP-layer
  switches the API carries.
- **Unfreeze.** A real product requirement (documented, with a user/business
  justification), then the breaking-change process in `versioning-policy.md`
  (this is what the first `/v1` release and its prefixed, tenant-nested target
  model are reserved for) and contract bump in the same change. Until then the
  snapshot is the contract.

## 9. Stop creating new architecture documents unless they resolve an actual implementation decision

- **What is frozen.** No new architecture documents, plans, or ADR-shaped
  essays. An architectural question is answered by the documents that already
  exist (see the reading order in `docs/architecture/README.md`). A new
  document (or ADR) is written only when an *actual implementation decision* —
  a concrete change under construction — cannot be expressed by the existing
  docs and requires the ADR path.
- **Evidence.** The architecture index below is complete and closed; the
  migration plan's step 8 confirmed every as-built/aspirational contradiction
  was resolved by *editing existing docs*, not writing new ones.
- **Unfreeze.** n/a — this is the process rule itself. Violations are review
  blockers.

---

## Enforcement

| Freeze item | Guard | Where it runs |
|---|---|---|
| 1–2 modular monolith + layer direction | `scripts/check_layer_boundaries.py`, `scripts/check_domain_purity.py`, mypy/ruff | CI |
| 3 PostgreSQL system-of-record | versioned DDL runner, integration tests | CI integration job, compose |
| 4 Redis queue | queue adapter behind ports, integration tests | CI integration job |
| 5 worker architecture | compose smoke (worker claims + persists), `probe` healthcheck | CI integration job |
| 6 evidence invariant | contract suite (evidence links), storage-level immutability | CI |
| 7 evaluator contract | plugin registry only path; ADR-004 trigger docs | review + ADR process |
| 8 API freeze | contract suite + OpenAPI snapshot | CI |
| 9 no new architecture docs | review rule: every doc addition must resolve an implementation decision | review |

## Change policy

- **Allowed without an ADR:** implementation inside a frozen item that stays
  within its boundary (a new deterministic evaluator, a migration, a bugfix —
  every one still subject to the smallest-correct-change rule and its gates).
- **Requires an accepted ADR + the item's unfreeze cost:** touching any frozen
  decision above. The ADR must name exactly what it revokes and the trigger
  that justifies it. Implementation does not start while the ADR is
  unaccepted (`docs/implementation/agent-implementation-guide.md` §ADR rule).
- **Requires the product requirement, then the API process:** §8. A
  "nice-to-have" is not a requirement; a requirement that forces a narrower
  API, not a broader one, is preferred.

## Supersedes

This document freezes, and does not replace, the authority chain:
`docs/README.md → docs/architecture/README.md → high-level → system-context →
container → component → development-architecture → read/write →
execution → evidence → security → data-flow → failure → ADRs`.

## Status

The freeze enters force immediately on this commit. Any future change that
violates a frozen item and is merged without its required ADR/product
requirement is a process violation and must be reverted or re-decided.