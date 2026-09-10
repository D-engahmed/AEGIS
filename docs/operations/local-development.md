# Local Development

This document describes how to run AEGIS locally for development and testing: prerequisites, local infrastructure, starting the API and workers, running migrations and tests, seeding demo data, and where logs and traces appear. Local development must never point at shared, staging, or production infrastructure, and never at a real tenant's data (`test-environments.md`).

## Prerequisites

- **Python**: version as pinned in the project config (the toolchain and lint/test commands are defined in `docs/development/coding-standards.md`). Use the project's virtual environment tooling as documented there.
- **Docker**: required to run local infrastructure containers (PostgreSQL, Redis, object storage). The local harness manages these containers (`test-environments.md`).
- **Optional local provider fixtures**: targets and models are represented by recorded fixtures or fake providers; no real LLM provider keys are required for the standard local test suites. If you intend to run a live experiment against a real provider, provider credentials are injected via the secrets provider — never via committed environment files (`secrets-management.md`).

## Directory Layout Map

The layout below is the representative structure derived from the traceability matrix (`docs/requirements/traceability-matrix.md`) and the modular-monolith design (`ADR-001`). Module paths shown are those referenced in the matrix; exact repository layout is to be confirmed in project config.

```text
aegis/
├── pyproject.toml / requirements files      # dependencies (SQLAlchemy, FastAPI, Redis, OTel SDK, ...)
├── docker-compose.yml                       # local infra: PostgreSQL, Redis, object storage (local)
├── local.env.example                        # non-secret local env template — NEVER commit secrets
├── src/
│   └── aegis/
│       ├── api/                             # interface layer: FastAPI application, REST surface
│       ├── app/                             # application layer: use cases, orchestration
│       ├── domain/                          # domain layer: entities, invariants
│       ├── infra/                           # infrastructure layer: PostgreSQL, Redis, object storage,
│       │   │                                #   OpenTelemetry, HTTP client, secrets client adapters
│       │   ├── db/                          # SQLAlchemy models, repositories, migrations
│       │   ├── queue/                       # Redis queue client (queue library to be confirmed)
│       │   ├── object_store/                # S3-compatible object storage client
│       │   └── secrets/                     # secrets provider client (Vault / KMS)
│       ├── execution/                       # execution layer: engine, retry, timeout, cancellation
│       ├── tracing/                         # trace collector, OpenTelemetry-compatible ingestion
│       ├── evaluation/                      # evaluation fabric: engine and metric plugins
│       ├── policy/                          # policy and gates layer
│       ├── evidence/                        # evidence layer: graph, provenance, artifact refs
│       ├── analysis/                        # analysis engine: regression, failure clustering
│       ├── observability/                   # observability layer: ingestion, export, health
│       ├── projects/                        # project service
│       ├── targets/                         # target registry
│       ├── datasets/                        # dataset service
│       └── experiments/                     # experiment service
├── workers/                                 # worker entry points (queue consumers)
└── tests/
    ├── unit/                                # unit tests (no infrastructure required)
    └── integration/                         # integration tests (require containers)
```

Exact entry-point module paths for the API and workers are to be confirmed in project config; the commands below follow the documented convention and are adjusted from the actual definitions if the project pins different paths.

## Bringing Up Local Infrastructure

Local infrastructure consists of the three stores the platform uses (`ADR-003`):

- **PostgreSQL**: transactional metadata and results (projects, targets, experiments, runs, metrics, results).
- **Redis**: the job queue, caching, distributed locks, and rate limits (`ADR-002`).
- **Object storage**: large artifacts — datasets, trace payloads, reports (S3-compatible, e.g. a local MinIO server or equivalent).

The local `docker-compose.yml` defines the stack for the stores AEGIS currently uses. Bring up the needed services with:

```text
docker compose up -d postgres redis
```

- **PostgreSQL** (`postgres:17-alpine`) listens on host port **5433** (the default 5432 is reserved for other local tooling); the local database, user, and password are `aegis`/`aegis`/`aegis` and the volume `aegis_pgdata` keeps data across restarts.
- **Redis** (`redis:7-alpine`) listens on host port **6380**.
- Both services run healthchecks; wait until `docker ps` shows them `healthy` before running integration tests.

Object storage and a trace collector are not required for the current vertical slice; they remain future work in the compose file.

The configuration for local connections comes from environment variables as defined in `configuration.md`. Use the non-secret template:

```text
cp local.env.example local.env
```

and then load it in your shell. The template contains no secrets.

## Environment Variables to Start the API and Workers

The AEGIS `Container` resolves its adapters from these variables (`src/aegis/interface/container.py`):

```text
AEGIS_DATABASE_URL=postgresql://aegis:aegis@127.0.0.1:5433/aegis
AEGIS_REDIS_URL=redis://127.0.0.1:6380/0
```

- Setting `AEGIS_DATABASE_URL` selects the PostgreSQL adapters (experiments, runs, executions, results, catalog, cancellations, evidence, provenance, artifacts, gate reports) and applies pending migrations on startup.
- Setting `AEGIS_REDIS_URL` selects the Redis-backed queue.
- When a variable is unset the in-memory adapter is used, so the CLI works without any infrastructure. Pass `None` explicitly to force the in-memory path.

No secret values belong in this set. Provider keys and other secrets are resolved from the secrets provider (`secrets-management.md`); local development normally uses fixtures and does not need them.

### Start the API

The API entry point is to be confirmed in project config. The command binds locally and serves the interactive API documentation at its `docs` route.

### Start the Workers

Start at least one worker process to execute experiments locally:

```text
aegis worker
```

`aegis worker` claims jobs from the queue (`--count N` processes at most N runs), builds a REST target client from the run's registered target version, executes the run through the engine, links evidence, and completes the job. Claims are at-least-once: a crash redelivers the job, and replay is safe because run execution is idempotent and evidence linking is deduplicated per metric result. Add `worker --watch` (with `--poll-seconds`) to keep the process alive, polling the queue forever — the compose `aegis` service runs `worker --watch` so the stack is a live worker, not a restarting one-shot. A job that raises outside the engine's retry envelope (for example a malformed target config) is abandoned and redelivered: watch mode logs `worker error (job abandoned): ...` and keeps polling rather than dying in a crash-loop; one-shot mode exits 1 so a wrapper sees the failure.

`aegis probe` reports on runtime health and is the container healthcheck. When `AEGIS_DATABASE_URL` / `AEGIS_REDIS_URL` are set it also pings those stores (exit 0 only when every configured store answers), so a container is marked unhealthy instead of crash-looping silently while the stores are down.

## Running Migrations Locally

Migrations are part of the schema-evolution discipline (`docs/data/schema-evolution.md`). The runner in `aegis.infrastructure.migrations` applies a versioned set of DDL steps inside transactions, tracked in `aegis_schema_versions`. Migrations run automatically when a PostgreSQL-backed container is constructed; to migrate an existing database explicitly:

```text
python -m aegis.infrastructure.migrations <dsn>
```

The migration boundary from the immutability rules applies everywhere, including local: a migration that would touch an immutable row is forbidden.

## Running the Test Suites Locally

The local test policy is defined in `test-environments.md`: local runs the unit suites and the integration suites against the compose containers. No real LLM is required — targets are deterministic HTTP fakes.

- **Unit tests**: require no infrastructure. `python -m pytest -m unit`
- **Integration tests**: require PostgreSQL and Redis containers to be healthy. `python -m pytest -m integration`. The suite (`tests/integration/`) rescans the schema from empty, round-trips every Postgres adapter, exercises FIFO/abandon/redelivery against the Redis queue, and proves a run executed by the queue worker survives a container restart — including a blocking policy gate and its override. Tests self-skip when the services are unreachable.

## Seeding Demo Data

A local seed command creates a synthetic demo workspace so you can exercise the product flow: a project, a registered target with a version, a locked dataset, and one or more experiments. Seeds:

- Never require real provider credentials (targets are fake providers or recorded fixtures).
- Create their own organization and project scoped to the local tenant.
- Are safe to re-run; seeding is idempotent where possible.

The exact seed command and fixture data location are to be confirmed in project config. After seeding, submit an experiment through the API or dashboard and watch a worker pick it up from the queue.

## Where Logs and Traces Appear Locally

- **Logs**: structured JSON logs with correlation IDs, written to stdout. The `AEGIS_LOG_LEVEL` variable controls verbosity. Logs go to the terminal that started the API or worker process.
- **Traces**: exported through the OpenTelemetry-compatible pipeline. If local trace export is configured, spans appear in the local trace backend; otherwise they appear as structured entries in the API/worker logs. The local default is to be confirmed in project config.
- **Metrics**: exported to the configured exporter; a `console` exporter is a practical local default so metric lines appear in stdout.

Local configuration must not route telemetry to shared or production exporters.

## Common Local Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| API starts but requests fail with connection refused | PostgreSQL and/or Redis not running | `docker compose up -d` and re-check container health; confirm `AEGIS_DATABASE_URL` and `AEGIS_REDIS_URL` point at the local ports |
| Migration fails on `permission denied` | Wrong local database user / database not created | Recreate the local database with the credentials in the compose file; re-run the migration command |
| Experiments stay `queued` and never run | No worker process running, or worker cannot reach Redis | Start a worker; confirm Redis connectivity; check worker logs for connection errors |
| Job fails repeatedly with retries exhausted | Target fixture unavailable or timeout misconfigured | Check per-test and per-target timeouts in the experiment configuration; confirm the local fixture endpoint is serving |
| Object storage uploads fail | Bucket missing or wrong endpoint/bucket names | Confirm the object-store endpoint and bucket match the local object server; create the bucket if startup did not |
| Traces missing from the trace backend | Local trace exporter not configured | Add the local trace exporter endpoint to `AEGIS_TRACE_EXPORTER_ENDPOINT` (to be confirmed in project config), or inspect structured logs |
| Structured logs show PII-like data | Sensitive content flowing into logs | This is a defect per security policy; stop, fix the logging path, and treat any confirmed leakage per `secrets-management.md` |
| Integration tests fail to find containers | Fast integration suite requires local infrap | Start `docker compose up -d` before running integration tests |
| Idempotency failures on retry | Fixture or worker produces duplicate records | Verify the execution ID and idempotency key path; report as a defect against `FR-EXE-05` |

## Related Documentation

- `configuration.md` — layered configuration and fail-fast validation
- `secrets-management.md` — how to inject real credentials when you cannot use fixtures
- `docs/testing/test-environments.md` — what runs in local vs CI vs staging
- `docs/data/schema-evolution.md` — migration discipline, including the immutability boundary
- `docs/requirements/traceability-matrix.md` — modules and integration gates