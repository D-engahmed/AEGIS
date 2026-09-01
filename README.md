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
| 3–5 | Interface, infrastructure adapters (memory/REST), execution engine+worker, evaluation plugins | ✅ partial (FastAPI interface + memory/REST adapters; Postgres/Redis adapters pending) |
| 6–11 | Analysis, gates (policy), evidence, observability, security | ✅ done (FastAPI interface wired; CI gates green) |

The full roadmap is defined in [`docs/implementation/implementation-order.md`](docs/implementation/implementation-order.md)
and traced against requirements in [`docs/requirements/`](docs/requirements).

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

Unit tests are marked `unit` (fast, pure, no external services).

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

> **Production note:** the engine's real stores — PostgreSQL (records), Redis
> (job queue), object storage (evidence) — do not yet have adapters in this
> release. The image runs the packaged, health-checked package standalone. Wire
> the store adapters in as they ship in the infrastructure layer.

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
docs/                    100+ files - requirements, ADRs, layers, CI/CD
Dockerfile               production image
docker-compose.yml       server deployment
docker/entrypoint.sh     container entrypoint (probe/version)
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