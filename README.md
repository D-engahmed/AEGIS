# AEGIS

**AI Evaluation, Reliability & Observability Platform**

> **Is this AI system actually good, safe, reliable, and getting worse over time?**

Aegis measures and verifies AI systems — it does **not** build agents, act as an LLM
gateway, or compete with the platforms that run them. It answers *"how do we know
those agents actually work?"* for anything ancient builds and runs.

```text
                  ┌───────────────────────────┐
                  │         YOUR AI APP       │
                  │   LLM / RAG / Agent / …   │
                  └─────────────┬─────────────┘
                                │  traces / test runs
                                ▼
       ┌──────────────────────────────────────────────────────┐
       │  CONTROL  │    EXECUTION    │        EVIDENCE        │
       │  authority, snapshots & decisions   immutable records│
       └──────────────────────────────────────────────────────┘
```

---

## Status

| Phase | Scope | State |
|-------|-------|-------|
| 0 | Scaffold: packaging, layer layout, gates, CI | ✅ done |
| 1 | Domain layer: tenancy, targets/versions (immutability), datasets (draft→lock), events, registry | ✅ done |
| 2 | Application layer (services, ports, evaluation service) | ✅ done |
| 3 | Interface: single `aegis` CLI (`version`/`probe`/`evaluate`/`worker`) + console script | ✅ done |
| 4 | Infrastructure: PostgreSQL + Redis adapters, migrations, in-memory fallbacks | ✅ done |
| 5 | Execution: engine + queue worker + REST target adapter + evaluator plugins | ✅ done |
| 6–11 | Gates (policy), evidence, observability, security | ✅ done (gates & immutable evidence proven; FastAPI/OTel are post-v0.1) |

The full roadmap is defined in [`docs/implementation/implementation-order.md`](docs/implementation/implementation-order.md)
and traced against requirements in [`docs/requirements/`](docs/requirements).

---

## What is verified (the vertical slice)

The persisted vertical slice is implemented and proven against live infrastructure
(`tests/integration/`, 18 tests, against the compose Postgres + Redis):

- **Queue worker** — runs submitted through `RunService` are claimed and executed
  by `aegis worker`; at-least-once redelivery with idempotent execution and
  deduplicated evidence linking.
- **Gates** — threshold gates (PASS / WARN / BLOCK) persist; a blocked run's report
  and override survive a container restart.
- **Containerized deployment** — `docker compose up -d --build` runs a live
  `worker --watch` (store-aware `probe` healthcheck). A run submitted inside the
  compose network was claimed by the composed worker, executed against a container
  target, and its run + 2 executions + 2 evidence rows committed to PostgreSQL.

Explicitly deferred (post-v0.1, not part of this slice): FastAPI REST surface,
OTel trace store, object-storage evidence, dashboards, FEXL.

---

## Getting started

```powershell
# create env
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"

# run all gates locally (same as CI)
.\.venv\Scripts\ruff check src tests scripts
.\.venv\Scripts\ruff format --check src tests scripts
.\.venv\Scripts\mypy src
.\.venv\Scripts\python scripts\check_domain_purity.py
.\.venv\Scripts\python scripts\validate_docs.py
.\.venv\Scripts\python -m pytest -m unit -q --cov=aegis
```

Unit tests are marked `unit` (fast, pure, no external services). Integration tests
are marked `integration` and need the compose stores healthy:

```powershell
docker compose up -d postgres redis   # wait until both are "healthy"
.\.venv\Scripts\python -m pytest -m integration -q
```

The `aegis` console script (registered as `[project.scripts]`) is the single CLI:
`aegis version`, `aegis probe`, `aegis evaluate <dataset> --target <spec>`,
`aegis worker [--watch]`. Postgres/Redis are selected by `AEGIS_DATABASE_URL` /
`AEGIS_REDIS_URL`; unset means in-memory adapters, so the CLI also works with no
infrastructure (`docs/operations/local-development.md`).

---

## Deploy to a server (Docker)

The repo ships a production image (`Dockerfile`), a compose file, and a CI
deploy workflow. It is ready to be built and run on a Linux VPS.

Local build and smoke test:

```bash
docker build -t aegis:latest .
docker run --rm aegis:latest probe    # -> aegis 0.1.0: import ok, N evaluators registered
```

Compose (fastest way to stand it up on a server):

```bash
docker compose up -d --build
```

The `aegis` service runs `worker --watch` and its `probe` healthcheck pings
PostgreSQL and Redis (`docker compose ps` shows it `healthy`). The engine's
stores are wired by env: `AEGIS_DATABASE_URL` (PostgreSQL: runs, executions,
results, evidence, gate reports) and `AEGIS_REDIS_URL` (job queue). Migrations
apply automatically on container startup.

Automatic deploy on every `main` push is wired in
[`.github/workflows/deploy.yml`](.github/workflows/deploy.yml): it SSHes to the
VPS, refreshes the repo, and runs `docker compose up -d --build`. Configure
these repository secrets under **Settings → Secrets → Actions**:

| Secret | Purpose |
|--------|---------|
| `VPS_HOST` | server hostname/IP |
| `VPS_USER` | SSH user with docker access |
| `VPS_PORT` | SSH port (default `22`) |
| `VPS_SSH_KEY` | SSH private key (ed25519 or RSA) |

Optional `AEGIS_TAG` and `AEGIS_APP_DIR` (default `/opt/aegis`) can be set as
workflow or environment variables. See `docs/ci-cd/deployment-strategy.md` for
the full staged-rollout and rollback policy.

> **Adapters:** the engine's real stores — PostgreSQL (records) and Redis (job
> queue) — are implemented and exercised by the integration suite and the
> containerized deployment above. Object storage (evidence artifacts) remains
> post-v0.1; artifacts are content-hashed in-process until that adapter ships.

---

## Architecture in one picture

Open [`docs/aegis-system-architecture.excalidraw`](docs/aegis-system-architecture.excalidraw)
in [Excalidraw](https://excalidraw.com) for the full diagram — three planes, every
component annotated, fill colors encode responsibility, and numbered lifecycle badges
walk the ①start-run → ⑦evidence-link flow.

Plane summary:

- **Control plane** — authority, snapshots, decisions. API gateway, auth & tenancy,
  target registry (versions freeze once referenced), dataset service (draft → lock),
  experiment service (snapshots once), policy & gates (PASS / WARN / BLOCK).
- **Execution plane** — running work against targets. Redis-backed job queue
  (ADR-002), isolated execution workers, target adapters, and the evaluation fabric
  of isolated evaluator plugins (ADR-004).
- **Evidence plane** — immutable verification records. OTel-compatible trace store
  (ADR-005), results, artifacts, and the evidence graph. Rule: **no score without
  evidence** — every score links execution → trace → evaluator → evidence.

Key decisions are recorded as ADRs in
[`docs/architecture/architecture-decision-records/`](docs/architecture/architecture-decision-records)
(modular monolith ADR-001, Redis queue ADR-002, plugin isolation ADR-004, trace store ADR-005).

---

## Repository layout

```text
src/aegis/               Python package (modular monolith)
  domain/                layer 01 · pure business logic, stdlib only
  application/           layer 02 · use-cases & orchestration
  interface/             layer 03 · REST/gRPC boundaries
  infrastructure/        layer 04 · PostgreSQL/Redis adapters
  execution/             layer 05 · workers & scheduling
  evaluation/            layer 06 · evaluator plugins
  analysis/              layer 07 · trends & root-cause
  policy/                layer 08 · gates & no-score-without-evidence
  evidence/              layer 09 · evidence graph & auditability
  observability/         layer 10 · OTel tracing/telemetry
  security/              layer 11 · authorization & audit
scripts/                 automation (purity gate, docs validation)
tests/unit/domain/       domain unit tests (marked unit)
tests/integration/       live suite against compose Postgres + Redis (marked integration)
docs/                    100+ files - requirements, ADRs, layers, CI/CD
Dockerfile               production image
docker-compose.yml       server deployment (postgres + redis + aegis worker)
docker/entrypoint.sh     container entrypoint (probe/version/evaluate/worker)
.github/workflows/       ci.yml (gates) + deploy.yml (VPS deploy)
```

**Domain purity constraint** (layer 01): domain code may import only the Python
standard library and its own submodules — no HTTP/SQL/Redis/FastAPI/Django/Celery or
provider SDKs. Enforced by `scripts/check_domain_purity.py`.

---

## Branching model

| Branch | Purpose |
|--------|---------|
| `main` | integration - everything merged here |
| `requirements`, `architecture`, `data`, `api`, `development`, `testing`, `implementation`, `operations`, `ci-cd` | review tracks per docs area |
| `layers/00…11-*` | per-layer sub-branches (named `layers/*` because git refs cannot nest under the existing `development` branch) |

---

## Productivity rules (how we work)

- **Mode 1 — build:** write code phase-by-phase, matching
  [`docs/implementation/implementation-order.md`](docs/implementation/implementation-order.md).
  Documentation is the source of truth; every change stays consistent with docs and
  `grilling.md`.
- **Mode 2 — tech:** adopt/adapt patterns from the grilling doc (isolation, evidence,
  cheap failures, no-leakage set hierarchy, action gates, countermeasure codification).
- **Mode 3 — lock:** when behavior is verified, lock it into tests + docs + ADRs.
- **Mode 4 — execution & score:** commit, push to the right branch, and report what
  executed + what scored/succeeded.

---

## Relationship with ancient

```text
ANCIENT         builds & runs AI systems
AEGIS           measures & verifies AI systems
```

The two projects are designed to be used together — Aegis turns Ancient's systems
into continuously measured, regression-checked products.

Detailed product design lives in the docs (start at
[`docs/README.md`](docs/README.md)) and the original grilling notes in
[`grilling.md`](grilling.md).