# Integration Testing

## Scope

Integration tests prove that AEGIS components work correctly with the real infrastructure they depend on, without external services that are expensive, nondeterministic, or untrusted.

```text
Application + PostgreSQL
Worker + Queue
API + Database
Plugin + Evaluator RPC
```

Concretely:

- **Application + PostgreSQL**: persistence behavior, transactions, immutable records, tenant scoping, and constraint enforcement against a real contained PostgreSQL instance.
- **Worker + Queue**: job claiming, processing, redelivery, retry, cancellation, and terminal-state semantics against the real Redis-backed queue.
- **API + Database**: request-to-persistence behavior end to end through the API, including the write pipeline, error mapping, and idempotency, backed by the real database.
- **Plugin + Evaluator RPC**: the ADR-004 isolation boundary — `evaluate()`, `validate()`, and `metadata()` crossing the plugin process boundary under realistic transport conditions.

## Principles

### Real, Contained Instances of Infrastructure

Integration tests use real instances of infrastructure components, not fakes: PostgreSQL and Redis run in contained test environments (for example, dedicated containers per workspace). Using the real thing catches schema drift, driver behavior, queue semantics, and transaction bugs that a fake hides. Containers are started and torn down by the test harness, never shared with a developer's local data, and never pointed at shared or production infrastructure.

### No Real LLM or Provider

Integration tests never call a real LLM or provider. Target and model interactions use recorded fixtures or fake providers that serve deterministic responses from disk. This keeps integration tests fast, cheap, deterministic, and auditable. Real-model behavior is explicitly tagged and scheduled elsewhere; an untagged test must not spend money or issue external AI calls.

### Migrations Are Exercised

The test harness runs the migration set from an empty schema on every integration environment. Migration execution is part of the test: a migration that corrupts existing data or cannot run forward fails the suite. Rehearsed migrations in staging extend this to production-shaped data.

### Idempotency and Retry Behavior Against the Real Queue

Retries must not duplicate side effects. Integration tests deliberately redeliver jobs, kill a worker mid-processing, and re-claim a job to prove the idempotency key prevents duplicate executions and duplicate records. Bounded retries, backoff, and the retryable versus non-retryable classification are verified against the real queue implementation.

### Isolation: Each Test Has Clean State

Each test starts from a known, clean state. The harness truncates or recreates tenant-scoped data between tests so no test depends on the side effects of another. Tests create their own organizations, projects, targets, and datasets and clean them up, reinforcing the tenancy model.

### Test Data Factories

Test data is created through factories, not hand-written SQL fixtures. Factories construct valid tenant-scoped objects (organization, project, target, target version, dataset, test cases, experiment) and make invalid variants easy to build for negative tests. Factories centralize how tenant ownership is set so every object is bound to the organization and project it belongs to.

### Tagging Expensive Suites

Integration suites that are slow or resource-heavy are tagged `expensive` and scheduled, not run on every commit. The default integration set stays fast enough for the CI sandbox. See `docs/testing/test-environments.md` for which suites run in which environment.