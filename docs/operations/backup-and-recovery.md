# Backup and Recovery

AEGIS's product is trust: reproducible scores backed by immutable evidence. A backup strategy that loses evidence, or a restore that rewrites immutable records, destroys that trust. The governing rule mirrors the operational stance: **recovery is verified by chaos testing and restore drills — recovery is tested, not assumed.**

## What to Back Up

| Store | Contents | Why it is backed up |
|---|---|---|
| **PostgreSQL** | Transactional metadata and results: organizations, projects, targets, datasets, experiments, executions, metric results, gate verdicts, audit log | The relational source of truth for the Evidence Graph and all invariants (`ADR-003`) |
| **Trace store** | Evaluation and production trace spans (OTel-compatible) | Evaluation traces are evidence and are retained as such (`ADR-005`); production traces are recoverable telemetry |
| **Object storage** | Large artifacts: dataset files, trace payloads, reports, red-team payloads, evidence payloads | The bulk of evidence; repositories of the big objects referenced by the Evidence Graph |
| **Configuration** | Defaults and environment-specific override files, feature flags, retention defaults, rate limits | Reproducing an environment after loss; configuration is code (`configuration.md`) |
| **Secrets metadata** | Secret references and scoping metadata (never the secret values themselves) | Enables re-provisioning; secrets themselves are recovered from the secrets provider and rotated on suspicion (`secrets-management.md`) |
| **Queue state / critical jobs** | Pending and in-flight job records as persisted in PostgreSQL execution state | The recovery path for the Redis queue: jobs are re-driven from execution records, not from the queue's own memory |

The job queue itself (Redis) is not treated as a durable backup target: it is at-least-once with survivability limits acknowledged in ADR-002. The durable source of truth for jobs is the PostgreSQL execution state, which records where each execution stopped (`failure-architecture.md`) and can resume or re-drive work after a queue loss.

## Backup Cadence and Retention

| Store | Cadence | Retention |
|---|---|---|
| PostgreSQL | Full base backup nightly + continuous WAL archiving; point-in-time recovery available | Base backups retained per the retention schedule (org-configurable); audit-log data follows the audit retention window (`retention-and-deletion.md`) |
| Trace store | Continuous export or periodic snapshot | Retention per data class: evaluation traces retained as long as referencing evidence/gates require; production traces on the shorter operational window |
| Object storage | Bucket versioning enabled; lifecycle-managed snapshots or periodic export | Version and lifecycle retention per bucket; evidence artifacts follow retention-and-deletion policy; legal holds pause deletion |
| Configuration | Versions in the repository (git history is the backup) | Forever in git; environment overrides per release |
| Secrets | No value backup; metadata references backed up | References only; never copies of values |

Backups must preserve the **relationships** between stores: a trace-store restore that does not match the PostgreSQL execution records breaks evidence linking. Backup manifests record the point-in-time coordinate (the backup set as a whole), and restore drills must exercise the coordinated set, not single stores in isolation.

## Backup Verification: Restore Drills

Backups are only as real as the last successful restore.

- **Regular restore drills**: restore drills run on a documented cadence against staging or a dedicated restore test environment. A drill restores the full coordinated set (PostgreSQL, trace store, object storage) and verifies checksums, evidence links, and the ability to serve results.
- **Verification, not existence**: a backup that cannot be restored is not a backup. The drill verifies that restored data passes integrity checks and that the Evidence Graph remains intact ("no score without evidence" holds on the restored copy).
- **Chaos linkage**: where applicable, chaos testing exercises restore-adjacent conditions — storage failure simulation and backup restoration are the test method for NFR-DURAB-01. Chaos findings about durability feed the backup design.
- **RPO/RTO proof**: each drill records whether the restore met the RPO/RTO targets below. A drill that missed RTO is a finding with an owner, not a footnote.

## RPO / RTO Targets

| Metric | Target | Notes |
|---|---|---|
| RPO - PostgreSQL | <= 15 minutes | Continuous WAL archiving; point-in-time recovery to the last consistent archive |
| RPO - Trace store | <= 24 hours | Or continuous export where the trace store supports it; evaluation evidence may warrant a lower bound |
| RPO - Object storage | ~0 for versioned storage | Bucket versioning plus replication; deletion is a versioned, recoverable event |
| RPO - Queue | Recoverable from PostgreSQL execution records | Jobs are re-driven; in-memory Redis state is tolerated as lossy |
| RTO - Critical path (API + metadata serving results) | <= 1 hour | Restore enough to serve existing evidence and results; restore + verify the relational store |
| RTO - Full production recovery | <= 4 hours | All stores restored, integrity verified, DR check passed |

These are targets to be confirmed against the production topology and validated by restore drills; they are not produced by a component — they are produced by a verified procedure.

## Recovery Procedures per Store

### Database Restore (PostgreSQL)

1. Quiesce or route traffic away from the affected environment; do not run application writes into a half-restored store.
2. Restore the base backup and replay WAL to the target point-in-time. Choose the recovery point that preserves the newest **immutable** records.
3. **Restore must never overwrite newer immutable data.** Evidence, historical results, and the audit log are write-once (`immutability-rules.md`). If the target database already contains records newer than the recovery point (for example, a partial failure rather than total loss), the restore merges forward: newer immutable rows are preserved and only missing or corrupt rows are backfilled. A blind overwrite that rolls back immutable history is a data-loss incident of its own.
4. Verify referential integrity, RLS policies, and the audit log tail; confirm the schema version matches the deploying code (`schema-evolution.md`).
5. Re-drive recovery: enqueue any jobs whose executions are recorded as `queued`/`retrying`/`running` and whose work was lost, using the execution ID and idempotency key so nothing duplicates. Executions already terminal and evidenced are not re-run.

### Queue State / Critical Jobs

1. Confirm how much of the Redis queue survived (flush/failover context). A total Redis loss drops in-memory queue state by design (ADR-002).
2. Sources of truth: PostgreSQL execution records in `queued`, `retrying`, and `running` states.
3. Re-drive: re-enqueue from execution records with their original execution IDs and idempotency keys. Retries honor bounded-retry policy; a redelivered job that already completed is skipped, never duplicated.
4. Verify: no duplicate executions, no duplicated side effects, and every job either completes or terminates in a classified failed/cancelled state.

### Object Storage

1. Confirm bucket health and what the versioning/replication state provides.
2. Restore missing or corrupt objects from versioned history or from the snapshot/export; re-target artifact keys exactly so Evidence Graph references still resolve.
3. Verify checksums and that no partial artifact was promoted to complete (a partial artifact must never be treated as complete).
4. Re-upload any evidence produced after the last verified state; reconcile artifact references in PostgreSQL/trace store so every score still links to its evidence.

### Secrets and Configuration

1. Configuration restores from git (a specific release commits the exact override set for an environment).
2. Secrets: re-provision references through the secrets provider. In a DR scenario any credential the lost environment held is treated as potentially exposed and rotated per `secrets-management.md`.

## Evidence and Immutability on the Recovery Path

- Backups must **preserve evidence immutability**: a backup of the trace store and object storage is a copy of evidence, not a separate mutable copy. Restoring it must not open a write path to historical records.
- Restore merges forward and never overwrites newer immutable data. This is checked in the database restore procedure and practiced in every restore drill.
- Backup and restore activity is recorded in the audit log where it mutates state; restore operations themselves are audited (who restored what, when, from which backup).

## Disaster Recovery Tiers Across Environments

| Tier | Backup obligation | DR posture |
|---|---|---|
| **Production** | Full obligation: coordinated backups, WAL archiving, bucket versioning + replication, restore drills on a schedule, RPO/RTO met | Fastest restore path; replicated stores; documented DR runbook; drills prove targets |
| **Staging** | Full obligation for parity: staging holds production-shaped data needed for chaos, load, and migration rehearsal | Same topology as production so a chaos/load result transfers and a DR procedure can be rehearsed there safely |
| **CI sandbox** | Minimal: ephemeral per-run stores | No backup obligation; stores are recreated per run; a failed ci environment is rebuilt, not restored |
| **Local** | None | Rebuild from `local-development.md`; local data is disposable |

Staging is where recovery is practiced destructively — the DR runbook is exercised against staging before it is trusted in production. Restore drills run in staging (or a dedicated restore test environment), never destructively against production.

## The Rule

Recovery is verified by regular restore tests, and by chaos testing where applicable. A backup strategy is not a document; it is the set of procedures that have recently, demonstrably, restored the system to a verified state. If it has not been restored, it has not been verified.

## Related Documentation

- `docs/architecture/architecture-decision-records/ADR-003` — what the relational and object stores hold
- `docs/architecture/architecture-decision-records/ADR-002` — queue durability bounds and dead-letter semantics
- `docs/data/immutability-rules.md` — the immutables a restore must never roll back
- `docs/data/retention-and-deletion.md` — retention windows backups must honor
- `docs/operations/incident-response.md` — the evidence-corruption and object-storage runbooks
- `docs/requirements/non-functional-requirements.md` — NFR-DURAB-01 durability target