# Configuration

## The Layered Configuration Model

AEGIS configuration is resolved from four layers, in order of increasing precedence. Later layers override earlier ones. Secrets are handled separately and never appear in config files.

```text
1. Defaults file (bundled and versioned with the code)
2. Environment-specific override files
3. Environment variables
4. Secrets injected separately at deploy/runtime (not part of the config file tree)
```

- **Defaults file**: shipped with the application, contains safe, environment-agnostic defaults for every configurable value. Versioned with the code so configuration and schema stay synchronized.
- **Environment-specific overrides**: files per environment tier (local, CI sandbox, staging, production) that override defaults for that tier. These are committed and reviewed like code, because they change behavior.
- **Environment variables**: per-process overrides (for example, local development and per-container overrides).
- **Secrets**: injected separately through the secrets provider at deploy or runtime. Config files and environment variables contain **references**, never secret values (`secrets-management.md`).

Exact file names, variable names, and the resolution precedence details are to be confirmed in project config; the model above is the documented contract.

## Fail-Fast on Invalid Configuration

Every service validates its configuration at startup and refuses to boot on invalid or missing required values:

- Unknown or mistyped configuration keys fail startup.
- Required values that are absent, malformed, or out of range fail startup.
- Valid-format-but-inconsistent values (for example, a timeout larger than the whole-experiment timeout) fail startup.
- Connection targets that must exist (database, queue, object storage) are verified or explicitly marked optional.

There is no "run anyway and discover the misconfiguration at runtime" default. A service that cannot prove it has a valid configuration is safer down than up. This supports the failure-architecture rule that deterministic failures are not retried: an invalid configuration is a deployment defect, not a transient condition. Fail-fast validation at startup also protects the immutable-write guarantees, because a control plane that boots with a stale or partial schema must never start writing.

## Configuration Schema for the Main Services

### API

| Group | Representative settings |
|---|---|
| Connection | Database URL, connection pool size and overflow, pool connection timeout |
| Auth | Identity-provider issuer and audience, API-key verification, rate-limit defaults for authentication failures |
| HTTP | Worker concurrency for async request handling, request timeouts, CORS policy (per environment) |
| Ingestion | Trace and telemetry ingestion endpoint configuration, redaction settings for prompt/output capture |

### Workers

| Group | Representative settings |
|---|---|
| Connection | Database URL (separate pool from the API), queue broker URL |
| Concurrency | Worker concurrency (processes/threads per worker), prefetch settings |
| Execution | Per-test timeout, per-target timeout, whole-experiment timeout defaults; grace period for cooperative cancellation and hard timeout |
| Retry | Maximum retry count per failure class, exponential backoff base and jitter range |
| Rate limits | Per-target concurrent-invocation limit, per-target retry budget (FR-EXE-06) |
| Sandbox | Tool-side-effect policy default (destructive tools disabled/sandboxed unless explicitly authorized), network policy for target invocation |

### Queue

| Group | Representative settings |
|---|---|
| Broker | Redis URL, Redis connection pool, queue names for jobs and dead-letter |
| Durability | Dead-letter queue routing for jobs that exhaust retries (ADR-002), visibility/release behavior |
| Backend | Optional result backend location |

### Store

| Group | Representative settings |
|---|---|
| Database | PostgreSQL connection, pool sizing, replication settings (standby/replica URLs where used) |
| Object storage | Endpoint, bucket names, credential reference (never the credential itself), region, replication setting |
| Trace store | Trace store endpoint, batch size and flush interval for high-volume span ingestion, retention for production-observability traces |

## Main Configuration Groups

The main configuration groups cover every external dependency and policy the platform honors. All of them resolve through the layered model; none of them contain secrets.

| Group | What it controls |
|---|---|
| **Database connection** | PostgreSQL connectivity, connection pooling, timeouts, replication/standby roles where configured |
| **Queue** | Broker URL, queue names, worker concurrency, retry policy (max retries, backoff base, jitter), dead-letter routing |
| **Object storage** | Endpoint, buckets, artifact key conventions, region and replication |
| **Trace store** | Trace ingestion endpoint, batch behavior, retention for production traces (evaluation traces are retained per evidence policy, `retention-and-deletion.md`) |
| **Auth / identity** | Identity-provider issuer and audience, service-account API-key verification, scopes, rate limits on authentication failures |
| **Observability exporters** | OTLP endpoints for traces and metrics, export interval, log format and level, exporter failure behavior (must degrade gracefully, never block request handling) |
| **Retention defaults** | Default retention per data class (traces, results, artifacts, datasets, reports, audit logs) as operational fallback; per-organization override is a tenant policy, not operator config |
| **Rate limits** | API request limits, per-target concurrent invocation limits, per-target retry budgets, abuse controls on repeated failures |

Feature flags are configuration-like switches that change behavior (for example, enabling or disabling an evaluator adapter, a redaction policy, or a gate path). Feature flags obey the same rules: they have safe defaults, are validated at startup, and any flag change that alters behavior passes review/PR gates.

## The Rule: Behavior-Changing Configuration Passes Review

Configuration that changes behavior is code. Changes to defaults, environment overrides, feature flags, retention defaults, rate limits, or gate thresholds must pass the same review/PR gates as code changes. The rule prevents three failure classes:

1. **Silent behavior drift** — an editor changes a timeout in an environment file and nobody reviews it.
2. **Environment divergence** — staging and production silently run different retry or rate-limit policies, invalidating the parity rule (`environments.md`).
3. **Untested production config** — a behavior change reaches production without having been exercised in staging or validated by the fail-fast checks.

Rotation of values that are not secrets (for example, buffer sizes or export intervals) is the same as any config change: reviewed, validated, and verified by the applicable environment still being able to boot.

## Related Documentation

- `secrets-management.md` — secrets are injected separately and never stored in config files
- `environments.md` — how per-environment overrides map to the tier model
- `local-development.md` — the local environment template and the variables used locally
- `docs/architecture/failure-architecture.md` — deterministic failures (including invalid configuration) are not retried
- `docs/data/schema-evolution.md` — configuration and schema stay synchronized across environments