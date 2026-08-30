# Data Documentation

This directory is the authoritative reference for how AEGIS stores, owns, governs, evolves, and deletes its data. It sits alongside `docs/architecture/` (which explains how data flows and which invariants the write path enforces) and translates those architectural decisions into concrete storage, schema, and lifecycle rules that every service, worker, and migration must obey.

The Evidence Plane is the reason most of these rules exist. Every score must be explainable by the evidence that produced it ("No score without evidence"). Data integrity is not a convenience in AEGIS; it is the mechanism by which results become trustworthy, reproducible, and auditable. If data can be silently altered, removed, or re-scoped, the platform's core guarantee collapses. The rules in this directory exist to prevent exactly that.

## Storage Architecture Summary

AEGIS uses three primary storage technologies plus one dedicated trace store, keeping each kind of data in the store best suited to it (ADR-003).

| Store | Holds | Purpose | Volatility |
|---|---|---|---|
| PostgreSQL | Metadata and results | Users, projects, targets, experiments, runs, metrics, results, audit log, configuration | Transactional, ACID |
| Redis | Operational state | Job queue, caching, distributed locks, rate limits | Ephemeral, recoverable |
| Object storage | Large artifacts | Large datasets, trace payloads, reports, attack payloads | Durable blobs, referenced by key |
| Dedicated trace store (ADR-005) | Traces and spans | OpenTelemetry-compatible span data for evaluation and observability | High-volume, retains evidence |

AEGIS is a **modular monolith** (ADR-001). These stores back a single application; they are not decomposed into per-service databases. PostgreSQL is the single source of truth for relational state, supports the ACID transactions that immutability and the evidence graph depend on, and is the candidate host for Row-Level Security as a defense-in-depth tenant-isolation control (grilling.md Q82-Q84; ADR-003).

The **dedicated trace store** (ADR-005) is intentionally kept separate from PostgreSQL. Traces are high-volume and, when they are evaluation evidence, must never be sampled away. They are written to the trace store in parallel with transactional metadata in PostgreSQL and linked to executions on a stable execution/trace ID. See `docs/architecture/evidence-architecture.md` and `docs/architecture/data-flow.md` for how the two write paths stay consistent.

## Core Rules This Folder Enforces

The documents in this directory all serve the same set of invariants. Every table, lifecycle, migration, or deletion policy below is subordinate to these rules.

1. **Immutability** — Versioned configuration and historical results are written once and never mutated. Immutables include Target Versions, Dataset Versions after lock, Experiment snapshots, Evaluator Versions, and Historical Results. Execution records and metric results are write-once. Evidence and artifacts are immutable. The audit log is append-only. To change an immutable, create a new version; never rewrite the old one. See `immutability-rules.md` and `docs/architecture/write-architecture.md` (Write Invariants).

2. **Versioning** — Anything that can affect an evaluation outcome is versioned: target, dataset, evaluator, prompt, judge model, configuration, and policy. Versioning preserves reproducibility so historical experiments retain their meaning.

3. **Tenant scoping** — Every tenant-owned record carries `organization_id` and `project_id`. Isolation is enforced at the API, storage, telemetry, and external-integration boundaries, not by application code alone. PostgreSQL RLS is a defense-in-depth candidate. See `data-ownership.md`.

4. **Data classification** — Data is labeled Public, Internal, Confidential, Restricted, or Regulated, and that label governs storage, access, redaction, and retention. See `data-ownership.md`.

5. **Retention** — Retention is configurable per data class and per organization. Deletion is auditable and role-gated. See `retention-and-deletion.md`.

6. **No schema change without a migration** — Every schema change requires a migration following the database change protocol, with CI migration gates. Migrations must never rewrite immutable historical rows. See `schema-evolution.md`.

## Document Index

| Document | Description |
|---|---|
| [database-design.md](database-design.md) | Relational design of the PostgreSQL metadata/results store: table groups by concern, key columns, ownership plane, immutability notes, conventions, and indexing/pagination strategy. |
| [er-diagram.md](er-diagram.md) | Entity-Relationship diagram of the core domain and a narrative of each relationship, centered on Test Execution and connected to the Evidence Graph. |
| [data-ownership.md](data-ownership.md) | Who owns which data: tenant ownership, data classification levels, a data-type to classification and access mapping, pipeline ownership, and AEGIS as a sensitive system. |
| [data-lifecycle.md](data-lifecycle.md) | End-to-end lifecycle of the main data classes (dataset, experiment, execution, metric result, evidence, audit log): permitted/forbidden actions and who may transition each stage. |
| [schema-evolution.md](schema-evolution.md) | Rules for changing the schema safely: migrations, additive vs destructive changes, versioning, backfilling, rollback, zero-downtime posture, and interaction with immutability. |
| [immutability-rules.md](immutability-rules.md) | The single source of truth for immutability: the verbatim immutables list, enforcement mechanisms, and what a user can do instead of changing an immutable. |
| [retention-and-deletion.md](retention-and-deletion.md) | Retention policies per data class, auditable role-gated deletion, soft vs hard delete, regulated-data controls, and storage-cost implications. |

## Plane Ownership

These documents reference the three planes and which plane owns each table group:

- **Control Plane** — identity, projects, targets, datasets, experiments, configuration/policies.
- **Execution Plane** — experiment runs, executions, execution events, and worker state.
- **Evidence Plane** — traces, evaluates/metric results, gate verdicts, evidence links, artifacts, and reporting/audit.

The trace store (ADR-005) is owned by the Evidence Plane and is documented as part of the storage model but is not part of the PostgreSQL relational design; it is documented in `docs/architecture/evidence-architecture.md` and `docs/architecture/data-flow.md`.

## Related Documentation

- `docs/architecture/write-architecture.md` — the Write Invariants that this directory translates into table and lifecycle rules.
- `docs/architecture/evidence-architecture.md` — the Evidence Plane and the "No score without evidence" law.
- `docs/architecture/architecture-decision-records/ADR-003` — the three-store selection (PostgreSQL/Redis/object storage).
- `docs/architecture/architecture-decision-records/ADR-005` — the dedicated trace store.
- `docs/implementation/database-change-protocol.md` — the mandatory process for every schema change.
- `docs/ci-cd` — the migration and quality gates that enforce schema discipline.
- `grilling.md` — the storage, tenancy, immutability, and retention decisions that precede this documentation.
