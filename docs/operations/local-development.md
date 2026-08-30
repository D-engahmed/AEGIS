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

The local `docker-compose.yml` defines a minimal stack for these services. Bring it up with:

```text
docker compose up -d
```

- PostgreSQL listens on the default local port; the local database name and user are set in the compose file and mirrored in the non-secret local environment template.
- Redis listens on its default local port.
- Object storage exposes both the S3 API endpoint and a console; the bucket used by the platform is created at startup or by the migration/seed step.

For the dedicated trace store (ADR-005), the local stack may include an OpenTelemetry collector or compatible local backend so traces are visible during development. The exporter endpoint used locally is to be confirmed in project config; if no local trace backend is configured, traces still appear in structured logs so spans remain inspectable.

The configuration for local connections comes from environment variables as defined in `configuration.md`. Use the non-secret template:

```text
cp local.env.example local.env
```

and then load it in your shell. The template contains no secrets.

## Environment Variables to Start the API and Workers

The canonical variable names are to be confirmed in project config, but the shape is defined by the configuration model (`configuration.md`):

```text
AEGIS_ENV=local
AEGIS_DATABASE_URL=postgresql+psycopg://<user>:<password>@localhost:<port>/<db>
AEGIS_REDIS_URL=redis://localhost:<port>/0
AEGIS_OBJECT_STORE_ENDPOINT=http://localhost:<port>
AEGIS_OBJECT_STORE_BUCKET=aegis-artifacts
AEGIS_TRACE_EXPORTER_ENDPOINT=http://localhost:<port>      # optional in local
AEGIS_OTEL_METRICS_EXPORTER=<console or OTLP endpoint>     # local default often console
AEGIS_LOG_LEVEL=INFO
```

No secret values belong in this set. Provider keys and other secrets are resolved from the secrets provider (`secrets-management.md`); local development normally uses fixtures and does not need them.

### Start the API

```text
uvicorn <entry-point-module>:<app> --reload --port 8000
```

The entry-point module path is to be confirmed in project config. The API binds locally and is available at `http://localhost:8000`; the interactive API documentation is served at its `docs` route.

### Start the Workers

The queue library is Celery, Dramatiq, or ARQ (`ADR-002`); the exact worker command is to be confirmed in project config. Conceptually:

```text
<queue-library-worker> worker --concurrency <N>
```

Workers consume evaluation jobs from the Redis-backed queue, invoke targets, collect traces, persist executions, and run evaluation and gates. Start at least one worker process to execute experiments locally. Worker concurrency defaults to the configured value; for local development a small concurrency (`1`-`4`) is sufficient.

## Running Migrations Locally

Migrations are part of the schema-evolution discipline (`docs/data/schema-evolution.md`) and must run against local PostgreSQL before tests and experiments. The migration runner is to be confirmed in project config; conceptually:

```text
<schema-management-command> upgrade
```

The migration boundary from the immutability rules applies everywhere, including local: a migration that would touch an immutable row is forbidden.

## Running the Test Suites Locally

The local test policy is defined in `test-environments.md`: local runs the unit suites and the fast integration suites against containers. No real LLM is required — targets and models are recorded fixtures or fake providers.

- **Unit tests**: require no infrastructure and run anywhere.
- **Integration tests**: require the local containers (PostgreSQL, Redis) to be up. The fast integration set covers the documented integration gates (for example tracer collection, retry policy, evidence graph, queue-backed job execution per the traceability matrix).

The exact command for each suite is to be confirmed in project config. Local test execution never calls a real model provider. Deterministic and fixture-based tests must pass before pushing; the same fast suite gates the change in CI (`test-environments.md`).

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