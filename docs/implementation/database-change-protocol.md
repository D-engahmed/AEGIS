# Database Change Protocol

## Purpose and Authority

This document is the mandatory process for every schema change in the AEGIS PostgreSQL database. It is governed by `docs/data/schema-evolution.md`, operates within the immutability boundary of `docs/data/immutability-rules.md`, and is enforced by the CI migration gates (`docs/ci-cd`). Because the schema is the mechanism that enforces provenance, immutability, tenant isolation, and the Evidence Graph (ADR-003), it cannot be changed casually. There is **no ad-hoc DDL**. Every schema change is a migration, and every migration follows the protocol below.

## The Eleven Rules of Schema Change

### Rule 1: Every Schema Change Needs a Migration

There is no direct schema edit in any environment — local, CI, staging, or production. A new table, column, constraint, index, type change, or backfill is delivered as a numbered, reviewed, tested migration. Raw `ALTER TABLE` executed at a console is forbidden in every tier. If you catch yourself "just adding a column locally to test", the correct action is to write the migration and run it through the local harness.

### Rule 2: Classify Additive vs Destructive

Every migration is classified before it is written:

```text
Additive     Adds a table, column, index, or constraint without altering or
             removing existing data or its meaning. Extra columns are nullable
             or defaulted so existing rows remain valid.

Destructive  Drops, renames, re-types, or re-interprets a column or table;
             changes a constraint in a way that rewrites or removes data.
```

Additive is the default path. If a destructive change seems necessary, first revisit whether the right answer is a **new version entity** rather than an alteration of an existing one (`docs/data/immutability-rules.md`). Destructive migrations require a danger review by an Owner/Admin/data steward before they can be applied to any shared environment.

### Rule 3: Write the Migration with up and down

Every migration ships with both directions:

- **up**: applies the change.
- **down**: reverses it, or — where reversal would touch immutable rows — documents the reason reversal is not permitted and what the safe forward fix is instead.

The `down` direction must never rewrite immutable rows. For destructive steps this means the old data is archived/exported before the destructive step executes, per the zero-downtime and rollback rules below.

### Rule 4: Review Destructive Migrations; May Require Human Approval

A destructive migration is not merged on author judgment alone. It requires:

1. An explicit danger review documenting what data is removed, renamed, or re-interpreted.
2. Confirmation that no immutable row is touched (write-once results, locked dataset versions, published target/evaluator versions, executed experiment snapshots).
3. An archival/export plan that reconstructs the old data if it is later needed.
4. Human approval by an Owner/Admin/data steward before application to staging or production.

Additive migrations still pass review, but they do not carry the danger-review requirement.

### Rule 5: NEVER Write to Immutable Historical Rows

A result is write-once. If a column must change meaning, type, or interpretation on a versioned entity:

```text
Do NOT alter the immutable row.
Create a new version entity (or new version number) carrying the new
interpretation. The old version stays exactly as published.
```

This rule protects the "old experiments silently change meaning" failure mode (grilling.md Q46). A migration that would rewrite historical results, a locked dataset version, a referenced target version, or a versioned evaluator to a new interpretation is forbidden in its entirety, not "forbidden but approvable". Backfills that would rewrite immutable rows are likewise forbidden; backfill applies only to non-immutable data.

### Rule 6: Migrations Are Tested in CI

Every schema change runs the CI migration gates (`docs/ci-cd`):

- **Migration tests**: the migration is run against a clean database and against a snapshot of the previous schema; it must apply forward, backfill correctly, and leave no drift. Destructive steps are asserted to be reversible-to-state through the archival path and to touch no immutable rows.
- **Integration tests**: after migration, application read/write paths still satisfy tenant isolation, evidence linkage, and immutability invariants (a result cannot exist without evidence; a locked dataset still cannot be modified).

A migration that is not part of the reviewed linear sequence, or that drifts from it, fails the gate. CI is the enforcement point for "no schema drift reaches the database".

### Rule 7: Order Relative to Code Deploy — Expand/Contract

Schema changes deploy in the expand/contract order so code and schema never disagree:

1. **Expand.** Add the new column/table as nullable or defaulted. Deploy code that writes and, optionally, reads the new structure. Code during the expand phase is backward compatible with the old schema.
2. **Dual-write (when needed).** For renames or semantic moves, write to both the old and new representation temporarily so reads remain valid during transition. Dual-write is an exception that requires explicit approval because it doubles write load and consistency responsibility.
3. **Backfill.** Populate the new representation from authoritative state — never from immutable interpretation changes.
4. **Cutover.** Flip reads to the new structure once it is complete and verified.
5. **Contract.** Remove the old representation only after no deployed code depends on it, and only when doing so touches no immutable rows.

The fixed invariant: during the expand phase, the code deployed is backward compatible; a code version never depends on a schema change that has not yet been applied, and a schema change is never counted on by code that has not yet been deployed.

### Rule 8: Backfill Steps

When a migration includes a backfill:

- Backfill only on **non-immutable** data; backfills that rewrite immutable rows are forbidden.
- Backfills are **deterministic and idempotent**, so re-running a failed migration does not double-apply or corrupt data.
- Backfill may run within the same transaction as the migration, or as a clearly-scoped follow-on step. Where the backfill is a separate step, it is documented with its idempotency guarantee and its verification query.

### Rule 9: Rollback of Migrations

Migrations are **forward-committed**, not blindly rolled back in production. The rules:

- Rollback uses the **contracting** leg of expand/contract (remove the backstop after the new code is fully deployed), not a blind reversal of a destructive step.
- If a migration is discovered to be wrong, the fix is a **new forward migration** that corrects state — never an undocumented reversal — because a reversal could rewrite immutable rows or lose audit continuity.
- Destructive steps are written so the old data can be reconstructed (archival export) before the destructive step executes, because some data is immutable and cannot be recreated.

The detailed runbook is `docs/implementation/rollback-protocol.md`; automated destructive-migration rollback is never permitted.

### Rule 10: No Raw Schema Edits in Environments

No operator, agent, or tool executes schema-changing SQL against a running environment. The migration sequence is the only writer of schema. If a schema change is observed in an environment that is not in the migration sequence, that is an incident and a security/reliability concern, not a cleanup chore. Schema drift is detected by the CI gates and must be reported.

### Rule 11: Versioned Entities Stay Versioned

For versioned entities (targets, datasets, experiments, evaluators, policies), changing how a version is interpreted is itself a versioned change. New fields that apply only to future versions are added with a null/absent default so historical rows remain valid and uninterpreted by the new field. The version table and its immutability semantics are never bent to retrofit history.

---

## The Protocol Steps for Any Schema Change

### 1. Determine Necessity

Is a schema change actually required? Often the answer is a new version entity, not a schema change. If the need is genuinely schema-level, proceed.

### 2. Classify

Additive or destructive, as in Rule 2. Record the classification in the migration.

### 3. Design the Migration

Write the numbered migration with `up`, `down`, classification, and (if destructive) the danger review inputs: data affected, immutability check, archival plan. The migration depends only on earlier migrations in the linear sequence.

### 4. Review

Additive migrations pass normal review. Destructive migrations additionally pass the danger review and human approval gate (Rule 4).

### 5. Commit Before Apply

The migration is reviewed and committed before it is applied to any shared environment. Migrations are applied in strict linear order; out-of-order application is rejected by CI.

### 6. Test in CI

The migration runs the migration tests and integration tests (Rule 6). No migration merges without them.

### 7. Deploy in Expand/Contract Order

The migration and its dependent code deploy per Rule 7. Dual-write requires explicit approval. Backfill runs per Rule 8 with idempotency and verification.

### 8. Verify

Post-migration verification queries confirm the schema matches the intended design and no data was corrupted or immutably rewritten. Any drift is a blocking defect.

### 9. Roll Back Correctly

If the release must roll back, follow `docs/implementation/rollback-protocol.md` and Rule 9. Contracting the backstop is the rollback mechanism; a blind destructive reversal is never it.

## Related Documentation

- `docs/data/schema-evolution.md` — the schema-evolution rules this protocol operationalizes.
- `docs/data/immutability-rules.md` — the immutability boundary every migration must respect.
- `docs/data/database-design.md` — the design schema changes must preserve.
- `docs/implementation/migration-protocol.md` — the operational runbook for applying migrations during a release.
- `docs/implementation/rollback-protocol.md` — how migrations and releases roll back safely.
- `docs/ci-cd` — the migration and quality gates that enforce this protocol.
- `docs/architecture/write-architecture.md` — the Write Invariants migrations must never weaken.
- ADR-003 — why PostgreSQL and schema discipline are a security and integrity concern.