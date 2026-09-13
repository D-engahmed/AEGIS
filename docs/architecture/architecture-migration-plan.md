# Architecture Migration Plan (Phase 1 — Audit)

Status: **audit complete, no behavior changed**. This document records the
as-built architecture of AEGIS at `main`, the target architecture, and the
ordered migration strategy. It is the required analysis before any
large-scale refactoring (see mission Phase 1).

Authority: layer placement and dependency permission come from
[development-architecture](development-architecture.md),
[../development/dependency-rules.md](../development/dependency-rules.md), and
the layer files under `docs/development/layers/`. API changes are governed by
[../api/versioning-policy.md](../api/versioning-policy.md) via
[../implementation/api-change-protocol.md](../implementation/api-change-protocol.md).
DB changes are governed by `docs/data/schema-evolution.md` via
[../implementation/database-change-protocol.md](../implementation/database-change-protocol.md).
Refactor conduct follows
[../implementation/definition-of-done.md](../implementation/definition-of-done.md)
(smallest correct change, docs stay consistent with code).

## 1. Current architecture (as-built)

AEGIS is a **modular monolith** (ADR-001:
[architecture-decision-records/ADR-001-modular-monolith-vs-microservices.md](architecture-decision-records/ADR-001-modular-monolith-vs-microservices.md)):
one Python package (`src/aegis/`, layers 01–11), one Docker image, deployed as
two services from the same image. No microservices, no Kafka, no Kubernetes —
and the audit found **no evidence any of them is needed**.

### 1.1 Runtime topology (verified in code + compose)

```text
Browser dashboard (frontend/, static server, :5173)
    |  HTTP + Bearer token, API base via window.AEGIS_API_BASE
    v
FastAPI API (src/aegis/interface/, :8000, `aegis serve`)
    |  application services over port Protocols
    v
Application (src/aegis/application/) -> Domain (src/aegis/domain/, stdlib only)
    |  ports (Protocols)                        in-memory or Postgres/Redis
    v                                            (AEGIS_DATABASE_URL / AEGIS_REDIS_URL)
PostgreSQL (records) + Redis (queue) <-- worker (`aegis worker --watch`)
    queue is the explicit contract between control plane and workers
```

- Compose wires four services: `postgres` (`5433:5432`), `redis`
  (`6380:6379`), `aegis` (`worker --watch`), `api` (`serve --port 8000`) —
  see `docker-compose.yml:8-81`. Both app services share one image
  (`Dockerfile:1-54`, healthcheck `aegis-entrypoint probe`).
- Entry points: `aegis` console script (`version`/`probe`/`evaluate`/`record`/
  `worker`/`serve`, `src/aegis/interface/cli.py`), ASGI `create_app()`
  (`src/aegis/interface/app.py:45-83`), typed SDK (`src/aegis_sdk/`, no
  `aegis.*` imports), dashboard (`frontend/`).
- Persistence: raw `psycopg` per-call connections, no ORM anywhere in `src/`
  (verified by grep: zero `sqlalchemy`/`Session`/`mapped_column` hits).
  Migrations are a versioned DDL runner
  (`src/aegis/infrastructure/migrations.py`, `aegis_schema_versions` table).
  Evidence artifacts stay content-hashed in-process until an object-storage
  adapter ships (`docker-compose.yml:1-6`).
- The dashboard is already a separate static deployable (`frontend/`,
  `window.AEGIS_API_BASE`, CORS opt-in via `AEGIS_CORS_ORIGINS`) and the API
  serves no UI assets (`src/aegis/interface/app.py:34-42,57-64,77-80`).

### 1.2 Layer map (packages as they exist)

| Layer | Package | Role | External deps actually used |
|---|---|---|---|
| 01 domain | `domain/` | entities, value objects, invariants, events, exceptions | stdlib only (verified clean) |
| 02 application | `application/` | use cases (`ExperimentService`, `RunService`, `EvaluationRunner`, `EvaluationService`, `RunGateService`) + ports | domain + capability concretions (see V2) |
| 03 interface | `interface/` (+ `schemas.py`, `deps.py`, `errors.py`, `container.py`, `cli.py`, `routers/`) | FastAPI routes, CLI, composition root, auth deps, error translation | FastAPI, Pydantic, psycopg/redis (health probes only) |
| 04 infrastructure | `infrastructure/` | memory + Postgres + Redis + REST-target + recordings adapters, serde, migrations | psycopg, redis, urllib (REST target) |
| 05 execution | `execution/` | cancellable engine loop, worker pump, retry/timeout/cancellation policies | ports + domain + observability |
| 06 evaluation | `evaluation/` | deterministic plugin registry + trajectory evaluators | domain only |
| 07 analysis | `analysis/` | Welch statistics, comparison, regression, trends, slicing, clustering | domain only (+ stdlib stats) |
| 08 policy | `policy/` | threshold/evidence gates, verdict store port | domain only |
| 09 evidence | `evidence/` | record factory, provenance hashing, in-memory graph, storage ports | domain + `security.models` |
| 10 observability | `observability/` | tracer, preservation engine, correlation, JSON logging, health, cost, OTLP exporter | httpx (OTLP only), no OTel SDK |
| 11 security | `security/` | HMAC tokens, RBAC, audit log, PII redaction, override predicate, ports | domain + `policy.models` |
| client | `aegis_sdk/` | typed sync REST client over httpx | httpx only |

### 1.3 Dependency map (aegis-internal imports only, verified)

```text
domain        -> (none; intra-package relative imports only)
application   -> domain, evidence, execution, evaluation, observability, policy
interface     -> domain, application, infrastructure (container only),
                 analysis, evidence, evaluation, observability, policy, security
infrastructure-> domain, application.ports, evidence.models, policy.models,
                 execution.cancellation (V2 below)
execution     -> domain, application.ports, application.run_tracing,
                 observability.models, observability.run_tracing
evaluation    -> domain
analysis      -> domain
policy        -> domain
evidence      -> domain, security.models
observability -> application.run_tracing (run_tracing.py only), else intra-package
security      -> domain, policy.models
aegis_sdk     -> (none; standalone httpx client)
```

Ports (`Protocol`s) live next to their capability:
`application/ports.py` (repositories, catalog, queue, target client, gateway),
`application/run_tracing.py`, `analysis/ports.py`, `policy/ports.py`,
`evidence/ports.py`, `security/ports.py`, plus `TelemetryExporter`/`HealthCheck`/
`CostTracker` in `observability/`. Most infrastructure adapters duck-type the
ports without explicit `class X(Port)` declarations, so mismatches surface at
runtime rather than under mypy.

## 2. Findings (prioritized, each with evidence)

### V1 — Routers own orchestration and reach past services (biggest)

- Catalog registration logic lives in the router with no `CatalogService`:
  `src/aegis/interface/routers/catalog.py:135-150` (target) and `:164-175`
  (dataset), duplicated in the CLI (`src/aegis/interface/cli.py:52-86`).
- Routers query stores directly instead of via application services:
  `src/aegis/interface/routers/runs.py:82-85`,
  `src/aegis/interface/routers/analysis.py:23,39-40,63-64`.
- Business rules hard-coded in routers:
  `src/aegis/interface/routers/analysis.py:102` (critical-severity filter),
  `src/aegis/interface/routers/policy.py:88` (override-target selection),
  `src/aegis/interface/routers/policy.py:99-115` (override + audit write).
- DTOs assembled in routers (`routers/experiments.py:75-81`) and raw domain
  reports returned without wire models (`routers/analysis.py:66-71`,
  `routers/observability.py:45-48,61-81`).
- The CLI re-implements the worker drain loop (`cli.py:277-305` vs
  `execution/worker.py:21-44` plus `application/runner.py:155-178`).

### V2 — Dependency-direction inversions and cycle risk

- `application/runner.py:43-46,62-116` depends on execution **concretions**
  (`ExecutionEngine`, `ExecutionWorker`, `RetryPolicy`, `TimeoutPolicy`);
  `infrastructure/memory.py:35` imports `execution.cancellation` — both point
  the wrong way (execution sits above application/infrastructure).
- Package-level cycle risk: application → execution → observability →
  application (`application/runner.py:43-46`, `execution/engine.py:18,32,52-56`,
  `observability/run_tracing.py:13`, `application/evaluation.py:23`). No
  module pair cycles today, but the ring is one careless import from closing.
- Function-level imports hide weight and intra-domain cycles
  (`domain/experiments.py:128,163`, `domain/execution.py:300,315`,
  `infrastructure/postgres.py` nine lazy imports, `interface/container.py`
  lazy adapter imports).
- Every router depends on the concrete `Container` rather than port-typed
  services (`routers/runs.py:23,38,55,66,78`); mitigated only because
  `Container` attributes are typed as `Protocol`s (`container.py:105-115`).
- `interface/app.py:86` instantiates the full `Container` at import time.

### V3 — DTO / schema / SDK triple mapping with no codegen

`application/dtos.py` (`RunView`), `interface/schemas.py` (`*In`/`*Out`),
and `aegis_sdk/models.py` describe the same wire shapes three times with
hand-written mappers (`routers/results.py:10-19`,
`routers/experiments.py:35-41,75-81`, `cli.py:484-500`). Any field change
must be edited in three places; nothing enforces parity today.

### V4 — Dead, empty, or suspicious surfaces (remove only with proof)

- Wired but never read: `container.py:171` (`evidence_graph`); cost ledger
  always `0.0` (`observability/cost.py:29-37` never called);
  `execution/timeout.py:31-37` (`test_timeout_remaining` unused).
- Empty `__init__` surfaces: `policy/`, `application/`, `infrastructure/`,
  `execution/`, `evaluation/`, `interface/routers/`. `observability/__init__.py`
  omits `OtlpSpanExporter`/`EvaluationTracerProvider` that the container needs.
- Misnamed module: `routers/results.py` defines no router, only a mapper.
- Debug endpoints `GET /policy/now`, `GET /security/now`
  (`include_in_schema=False`) with no documented purpose.
- Pre-existing security hardening notes (out of migration scope, do not
  silently change): `GET /security/dev-token` mints arbitrary-role tokens
  behind `AEGIS_DEV_LOGIN=1` (`routers/security.py:22-49`); `AUTH_SECRET` is
  hard-coded (`container.py:60`); tenant org is synthesized per-request, never
  looked up (`deps.py:53-60`).

### V5 — Docs contradict code in at least ten places (docs-only fixes)

1. `/v1/...` prefix required by `../api/versioning-policy.md:5-15` and
   `../api/api-design.md:138-155`, but every router is unprefixed
   (`routers/runs.py:17`, `experiments.py:22`, `catalog.py:29`, …) and the
   dashboard calls unprefixed paths. **Resolution: document the as-built
   flat routes; do NOT rename routes without the versioning process.**
2. Nested tenant URLs (`/organizations/{id}/projects/{id}/...`,
   `api-design.md:5-19`) vs flat implemented routes.
3. Async contract (`POST /experiments/{id}/runs → 202 + status_url`,
   `async-execution-contract.md:19-32`) vs implemented `POST /runs → 201`.
4. Dashboard "optional / later / Next.js" (`container-architecture.md:90-95`)
   vs shipped static dashboard (`frontend/`, `../usage.md:30-61`).
5. Dashboard binned as "interface layer"
   (`docs/development/layers/00-system-boundaries.md:110-114`) vs separate
   deployable (`container-architecture.md:43`).
6. Interface status "CLI only" (`../../README.md:33`) vs full FastAPI surface.
7. OTel trace store / object storage described as present (ADR-005,
   `container-architecture.md:76-88`) vs deferred in `../../README.md:58-59`.
8. Three answers for who evaluates gates (API process vs worker vs Policy
   Service: `container-architecture.md:39-40`,
   `execution-architecture.md:39-48`, `component-architecture.md:71-85`).
9. Execution "no independent deployment boundary"
   (`docs/development/layers/05-execution-layer.md:63-65`) vs separately
   deployable workers (ADR-001, compose `aegis` service).
10. Evaluator RPC isolation (ADR-004) vs in-process plugin registry in code.
11. Cross-cutting observability/security ("may apply at every layer") vs
    layer files forbidding them from layers 03/05/06.
12. `../../README.md:30-36` marks phases 0–11 done while deferring OTel,
    object storage, FEXL post-v0.1.

### V6 — CI / test gaps (no behavior change, gates only)

CI (`../../.github/workflows/ci.yml:9-30`) enforces ruff, format, mypy,
domain purity, docs links, and unit tests (275 passing). It does **not**
enforce: integration tests (19 exist, self-skip without compose),
`contract`/`e2e` markers (declared in `pyproject.toml:35-40`, collect 0
tests), migration-safety checks, OpenAPI parity, security scans, coverage
floors, or any architecture rule beyond domain purity. Files named
`test_e2e_*` are marked `unit` and are not end-to-end coverage.

## 3. Target architecture

Keep the **modular monolith** (ADR-001 stands — reaffirmed, not replaced).
The target is the mission's layering with the direction:

```text
frontend -> API -> application -> domain -> ports -> infrastructure
```

Concretely:

- `frontend/` stays a separate static deployable talking only to the API
  (already true; locked by `tests/unit/interface/test_frontend_structure.py`).
- Routers become thin: HTTP validation, auth deps, DTO mapping, error
  translation. All orchestration moves to application services behind ports.
- `application/` depends on `domain` + port `Protocol`s + capability ports;
  execution concretions are injected, never imported.
- `infrastructure/` adapters declare the ports they implement
  (`class X(Port)`) so mypy enforces parity.
- Capabilities keep their packages (`evaluation/`, `execution/`,
  `evidence/`, `policy/`, `analysis/`, `security/`, `observability/`); no
  per-capability `domain/application/api/data/tests/` split until a
  capability proves it needs it (none does today — a premature split would
  be churn, not architecture).
- No new services, no Kafka, no Kubernetes, no event bus. The Redis queue
  remains the single async contract between control plane and workers.

## 4. Dependency rules (enforced, not just documented)

1. `domain/` — stdlib + intra-domain only (already gated by
   `scripts/check_domain_purity.py`; keep).
2. `application/` — `domain` + ports only. No imports of `interface/`,
   `infrastructure/`, or execution concretions.
3. `interface/` — `application` services/ports, `schemas.py`, `deps.py`,
   `errors.py`. Routers must not touch stores, build domain aggregates from
   wire payloads inline, or embed filter/severity rules.
4. `infrastructure/` — implements ports explicitly; never imports
   `interface/` or `execution/` concretions.
5. `execution/` — `application.ports` + `domain`; observability only through
   the `RunTracer` port seam.
6. Capabilities (`evaluation/`, `analysis/`, `policy/`, `evidence/`,
   `security/`, `observability/`) — `domain` + their own ports; cross-capability
   use goes through the importing capability's declared port, never a
   concretion import.
7. No function-level imports that hide cycles without a comment justifying
   them; new cross-package imports need a port first.
8. `aegis_sdk/` stays dependency-free of `aegis.*`.

## 5. Migration order (small, reviewable, reversible steps)

1. **Phase 2 — Freeze behavior.** Run the full gate
   (ruff, format, mypy, domain purity, docs validation, unit, integration
   with compose stores, Playwright E2E) and record the baseline below. No
   refactor starts from a red baseline without documenting the failure.
2. **Policy router thinning (smallest capability slice).** Move override
   orchestration + audit metadata (`routers/policy.py:99-115`) and the
   severity-selection rule (`:88`) into `RunGateService`; routers keep
   validation + mapping. Gate: unit + E2E policy flow.
3. **Catalog service extraction.** Introduce a catalog application service
   covering `routers/catalog.py:135-175` and retire the `cli.py:52-86`
   duplication; one implementation, two callers. Gate: unit + E2E catalog flow.
4. **Worker/CLI drain unification.** Route `cli.py drain_queue` through
   `ExecutionWorker.process_next` + `runner.finish_run` (the canonical path
   at `runner.py:150-153`); delete the fused copy. Gate: integration worker
   tests + E2E run-to-terminal.
5. **Execution concretions behind ports.** Inject engine/worker/retry/timeout
   as ports into `EvaluationRunner`; fix the `infrastructure → execution`
   import. Gate: mypy + unit + integration.
6. **DTO parity.** Centralize mappers per capability (keep hand-written
   mappers; no codegen dependency — stdlib-first principle,
   `dependency-rules.md:71-77`); add contract tests asserting schema ↔
   domain ↔ SDK parity. Gate: new `contract` marker suite in CI.
7. **Dead-code removal.** Delete only what tests prove unread
   (`evidence_graph` wiring, cost stubs or wire them, timeout helper,
   debug `now` endpoints or document them) — one deletion per commit.
8. **Architecture tests to CI.** Extend the purity script (or add one
   beside it) with the §4 rules: no store access from routers, no
   execution concretions in application, explicit port declarations.
   Add integration + contract jobs to CI with compose services.
9. **Docs triage.** Resolve §V5 contradictions as docs-only commits against
   the as-built code (routes stay flat; status sections updated). No
   behavior change rides along with a docs fix.

Explicitly **not** doing: per-capability `domain/application/api/data`
resplit, `backend/`-style repo reshuffle, `data/` package rename,
microservices, Kafka, Kubernetes, Terraform, OTel SDK adoption, object
storage — none is justified by the audit.

## 6. Compatibility strategy

- The OpenAPI-documented wire surface does not change in any migration
  step; refactors are internal (service extraction, import redirection,
  mapper centralization).
- Flat unprefixed routes stay until the versioning policy process
  (`../api/versioning-policy.md:30-40`) explicitly versions them — a rename
  is a breaking change and is out of scope for this migration.
- Every step must keep green: `ruff check`, `ruff format --check`, `mypy
  src`, domain purity, docs validation, `pytest -m unit`, `pytest -m
  integration` (compose stores healthy), and the Playwright dashboard E2E.

## 7. Risk assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Router thinning changes error shape | medium | high | keep `errors.py` mapping untouched; E2E + SDK tests pin shapes |
| Cycle closes application ↔ execution | medium | high | §4 rule + arch test before moving code (step 8 can precede step 5) |
| Catalog dedupe changes CLI behavior | low | medium | `record`/`evaluate` CLI tests + integration flows pin behavior |
| Dead-code deletion removes a live path | low | high | one deletion per commit; grep + coverage proof in message |
| Docs triage "fixes" code by accident | low | high | docs-only commits, zero `src/` changes, validate_docs gate |
| Scope creep into resplits/services | medium | medium | every change answers mission §24 questions in its message |

## 8. Rollback strategy

- One logical change per commit, each pushed green; rollback is `git revert`
  of a single commit (see [../implementation/rollback-protocol.md](../implementation/rollback-protocol.md)).
- Database: additive-only migrations; never auto-reverse destructive ones.
  No migration ships in this plan until a capability step requires one —
  none currently does.
- If a step breaks the gate, fix forward only for trivial causes;
  otherwise revert and re-plan the step.

## 9. Baseline (Phase 2, recorded at audit time)

To be filled by the Phase 2 run: ruff, format, mypy, domain purity, docs
validation, unit count, integration count (compose stores), Playwright E2E
result, plus any pre-existing failure with its evidence. No migration step
may start from an unrecorded baseline.

## 10. Definition of done for the migration

Per [../implementation/definition-of-done.md](../implementation/definition-of-done.md)
and mission §22: behavior preserved (gates green at every commit),
routers thin, application port-clean, domain still stdlib-only, execution
separated from request handling, evaluation/evidence/policy ownership
explicit, arch tests in CI, docs matching the as-built system, no new
services or technologies without an ADR.
