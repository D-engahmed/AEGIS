# AEGIS Operations

This folder is the operational reference for deploying, configuring, running, monitoring, troubleshooting, and recovering the AEGIS control plane. It is the operator-facing counterpart to the architecture, development, and testing documentation: `docs/architecture/` defines how AEGIS is built, `docs/development/` defines how it is changed, `docs/testing/` defines how it is verified, and this folder defines how it is operated and how reality is verified against the design.

AEGIS is an AI Evaluation, Reliability & Observability Platform: a modular monolith control plane that evaluates, tests, observes, secures, and verifies AI systems such as LLM applications, RAG pipelines, and agents. Operators are responsible for the platform that issues those verdicts, so the platform's own reliability is a first-class product property. A reliability control plane that cannot prove its own reliability is not trustworthy.

## Who This Is For

- On-call engineers and SREs responding to alerts and incidents.
- Operators who deploy, configure, scale, and back up the control plane.
- Anyone running AEGIS locally for development or testing.
- Security responders handling secret leakage, tenant-isolation suspicion, or evidence-integrity incidents.

## The Operational Stance

Four principles govern every operational decision:

1. **Fail contained, retry deliberately, never silently duplicate side effects.** Failures are classified before reaction. Retries are bounded, spaced with exponential backoff and jitter, and made safe by idempotency keys and unique execution IDs. A redelivered job never creates a duplicate execution, a second set of records, or a repeated external effect (grilling.md Q200; `failure-architecture.md`).
2. **Recoverability is verified by chaos testing and restore drills, not assumed.** Workers are killed, the queue is taken down, database connections are severed, and providers are blacked out in staging to prove the failure architecture holds. Backups are verified by restore drills, not by existing. If recovery is not tested, it has not happened.
3. **Observability is first-class.** AEGIS observes the AI systems it evaluates and observes itself. The signals that matter are measured continuously: worker latency, queue depth, evaluator failures, evaluation cost, API latency, database health, and trace ingestion (`observability.md`).
4. **No score without evidence, no recovery without verification.** Evidence is preserved on every failure path. Deletion and restore never corrupt or overwrite immutable records. Every incident is fed back into the failure architecture, testing strategy, and chaos program.

## Index

| File | Purpose |
|---|---|
| `local-development.md` | How to run AEGIS locally for development and testing: prerequisites, infrastructure via containers (PostgreSQL, Redis, object storage), starting the API and workers, migrations, test suites, seeding demo data, local logs and traces, and a troubleshooting table. |
| `environments.md` | Environment tiers (local development, CI sandbox, staging, production), what may run in each tier, access control, data fixtures, and the promotion flow with gates. |
| `configuration.md` | The layered configuration model, per-service configuration groups (database, queue, object storage, trace store, auth, exporters, retention, rate limits), feature flags, and the fail-fast validation rule. |
| `secrets-management.md` | What counts as a secret, where secrets live, secret injection, rotation and revocation, least-privilege scoping, and the secret-leak incident path. |
| `observability.md` | The observability posture, SLO-able signals and the metric catalog with thresholds, logging conventions, OpenTelemetry export, dashboards to build, and alerting. |
| `incident-response.md` | Severity levels, on-call structure, the incident lifecycle, communication, and the runbook list for the known failure classes. |
| `backup-and-recovery.md` | What is backed up, backup cadence and retention, RPO/RTO targets, verification by restore drills, and recovery procedures for each store. |

## Quick-Runbook Pointers

| What you need | Where to look |
|---|---|
| Environment tiers and what may run where | `environments.md` |
| Configuration model and required variables | `configuration.md` |
| Secrets, injection, rotation, leak handling | `secrets-management.md` |
| Dashboards, metric thresholds, alerts | `observability.md` |
| Incident response and the runbook list | `incident-response.md` |
| Backup cadence, restore, DR targets | `backup-and-recovery.md` |
| Local setup for development and testing | `local-development.md` |

## Feedback Loop

Operations verifies reality. Postmortems feed back into `docs/architecture/failure-architecture.md`, `docs/testing/chaos-testing.md`, and the CI/CD gates. A production finding that cannot be explained by the failure architecture is a documentation or design defect, not an excuse. If a chaos finding exposes a violated invariant, the failure architecture is fixed or the invariant is clarified (`chaos-testing.md`).