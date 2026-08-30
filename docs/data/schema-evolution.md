# Schema Evolution

This document defines the rules for changing the AEGIS PostgreSQL schema safely. Because the schema is the mechanism that enforces provenance, immutability, tenant isolation, and the Evidence Graph (ADR-003), it cannot be changed casually. Every schema change is a controlled, reviewed, and tested migration.

## The Cardinal Rule: Every Schema Change Needs a Migration

There is **no ad-hoc DDL**. Every schema change — a new table, a new column, a constraint, a type change, an index, a backfill — is delivered as a migration following `docs/implementation/database-change-protocol.md`. The protocol governs how migrations are written, numbered, reviewed, and applied. CI enforces that no schema drift reaches the database (see `docs/ci-cd` migration gates): a migration that is not part of the reviewed sequence fails the gate.

## Additive vs Destructive Changes

| Category | Definition | Posture |
|---|---|---|
| **Additive** | Adds a table, column, index, or constraint without altering or removing existing data or its meaning. Extra columns are nullable or defaulted so existing rows remain valid. | Safe by default; still requires a migration and passes through the normal protocol. |
| **Destructive** | Drops, renames, re-types, or re-interprets a column/table; changes a constraint in a way that rewrites or removes data. | Requires explicit migration plus a danger review by an Owner/Admin/data steward. A destructive change that would touch **immutable rows** is forbidden (see below). |

Additive changes are the default path. If a destructive change seems necessary, revisit whether the better answer is a **new version entity** rather than altering an existing one (`immutability-rules.md`).

## Versioning Approach for Versioned Entities

Versioned entities (targets, datasets, experiments, evaluators, policies) use a **base entity plus a version table**, as described in `database-design.md`. The implication for schema evolution:

- **Changing how a version is interpreted is itself a versioned change.** If the meaning of a field on a version table must change, you do not rewrite historical versions — you create a **new version entity** (or new version number) that carries the new interpretation.
- **Historical versions are snapshots.** Their columns remain fixed at the time of publication. New fields that apply only to future versions are added with a null/absent default so historical rows remain valid and uninterpreted by the new field.

This is the mechanism that keeps old experiments from silently changing meaning when the schema evolves.

## Backfilling

- A migration may run a backfill to populate new columns for **non-immutable data** (for example, denormalizing an index hint onto mutable project rows) **within the same transaction** or as a clearly-scoped follow-on step per the protocol.
- **Backfills that would rewrite immutable rows are forbidden.** Historical results and locked dataset versions are never backfilled into new interpretations.
- Backfills must be deterministic and idempotent so re-running a failed migration does not double-apply or corrupt data.

## Migration Order

Migrations are applied in a strict, linear, ordered sequence. Rules:

1. **Commits precede application.** A migration is reviewed and committed before it is applied to any shared environment.
2. **One source of truth for order.** The migration sequence is authoritative; a migration may depend only on migrations earlier in the sequence.
3. **Expand before contract.** New columns/tables are added before anything that would depend on them is deployed, enabling the zero-downtime pattern below.
4. **CI validates.** The CI migration gates (`docs/ci-cd`) run migrations against a clean database, verify forward drift is empty, and reject out-of-order or unreviewed migrations.

## Rollback Rules

- Migrations are **forward-committed, not randomly rolled back in production.** Rollback uses the **contracting** leg of the expand/contract pattern (remove the backstop after the new code is fully deployed), not a blind reversal of a destructive step.
- If a migration is discovered to be wrong, the fix is a **new forward migration** that corrects state, never an undocumented reversal, because reversing could rewrite immutable rows or lose audit continuity.
- Destructive steps are written so the old data can be reconstructed (archival export) before the destructive step executes, because some data is immutable and cannot be recreated.

## Zero-Downtime Posture

AEGIS uses the **expanding/contracting pattern** to deploy schema changes without downtime or breaking reads:

1. **Expand.** Add the new column/table as nullable or defaulted. Deploy code that writes and, optionally, reads the new structure.
2. **Dual-write (when needed).** For renames or semantic moves, write to both the old and new representation temporarily so reads remain valid during transition.
3. **Backfill.** Populate the new representation from authoritative state (never from immutable interpretation changes).
4. **Cutover.** Flip reads to the new structure once it is complete and verified.
5. **Contract.** Remove the old representation only after no code depends on it, and only when doing so touches no immutable rows.

Dual-write is used when a transition period is required; it is an exception that requires explicit approval in the protocol, because it temporarily doubles write load and consistency responsibility.

## How Migrations Interact with Immutability

Immutability is a hard boundary for schema evolution:

- **A migration must never rewrite immutable historical results.** There is no legitimate schema change that mutates historical metric results, locked dataset versions, published target/evaluator versions, or executed experiment snapshots to a new interpretation.
- **If a column must change meaning or type, create a new version entity** rather than altering an immutable one. The old version stays as-is; the new version carries the changed definition. This is the only correct path when immutability would otherwise be violated.
- Additive columns on version tables are acceptable **only** if they do not reinterpret existing rows (they are null/absent for historical rows and apply only to future versions). Any such addition is still reviewed to confirm it does not change the meaning of published data.

This rule is non-negotiable because it protects the "old experiments silently change meaning" failure mode (grilling.md Q46; `immutability-rules.md`).

## Referenced Decisions

- **ADR-003** — PostgreSQL is the single source of truth for relational state and the host for RLS; schema discipline is therefore a security and integrity concern, not just a maintenance convenience.
- **`docs/implementation/database-change-protocol.md`** — the mandatory, detailed process for every migration (commits, review, numbering, application, backfill, rollback).
- **`docs/ci-cd`** — migration and quality gates that enforce the protocol and reject schema drift.
- **`docs/architecture/write-architecture.md`** — the Write Invariants that the schema encodes and that migrations must never weaken.

## Test Strategy for Migrations

Migrations are tested like code:

- **Migration tests.** Each migration is run against a clean database and against a snapshot of the previous schema to verify it applies forward, backfills correctly, and leaves no drift. Tests assert that destructive steps are reversible-to-state (archival) and that no immutable rows are touched.
- **Integration tests.** After migration, integration tests verify that application read/write paths still satisfy tenant isolation, evidence linkage, and immutability invariants (a result still cannot exist without evidence; a locked dataset still cannot be modified).

The CI migration gates run both classes of test on every change that touches the schema.

## Related Documentation

- `docs/data/immutability-rules.md` — the immutability boundary that constrains all schema evolution.
- `docs/data/database-design.md` — the design that schema changes must preserve.
- `docs/implementation/database-change-protocol.md` — the concrete migration process.
- `docs/ci-cd` — the migration and CI gates.
- `docs/architecture/architecture-decision-records/ADR-003` — the storage selection that makes the schema the enforcement mechanism.
