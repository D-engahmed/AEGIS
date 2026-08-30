# Migration Protocol

## Purpose

This document is the operational runbook for applying data migrations and code/data migration steps during an AEGIS release. It is the execution half of `docs/implementation/database-change-protocol.md`: that protocol defines how a migration is written and reviewed; this protocol defines how it is operated — prepped, rehearsed, executed, verified, and aborted. It covers both pure schema migrations and the code/data migration steps that accompany them (backfills, dual-write windows, cutovers).

## The Expand/Contract Pattern (Narrative)

A schema change that must not break running code is executed as two legs that are never swapped:

1. **Expand.** Deploy the additive part of the schema and the code that writes (and optionally reads) the new representation. The code deployed here is backward compatible: it works against the old schema, because the new column/table is nullable and does not change existing data's meaning yet.
2. **Dual-write (only when required).** For renames or semantic moves, write to both the old and new representation so reads remain valid during the transition. This is an approved exception, never the default, because it doubles write load and consistency responsibility.
3. **Backfill.** Populate the new representation from authoritative state, deterministically and idempotently. Backfills never interpret immutable rows.
4. **Cutover.** Flip reads to the new structure once it is complete and verified.
5. **Contract.** Remove the old representation only after no deployed code depends on it, and only when doing so touches no immutable rows.

The invariant carried through every step: at no instant is a deployed code version dependent on a schema change that has not been applied, and at no instant does a schema change get counted on by code not yet deployed.

## Pre-Migration Checklist

Before any migration step runs in a shared environment, all of the following must be true:

```text
[ ] Migration is committed and part of the reviewed linear sequence.
[ ] Additive/destructive classification is recorded.
[ ] Destructive migration has passed danger review and human approval.
[ ] Immutability check complete: migration touches no immutable rows.
[ ] CI migration gates passed (forward apply, previous-schema apply, no drift).
[ ] Migration rehearsal ran on staging against production-shaped data.
[ ] Backup plan confirmed (see Backups below).
[ ] Verification queries written before execution.
[ ] Abort conditions and abort owner defined.
[ ] Communication plan defined (who is notified if the migration is slow or fails).
```

## Backups

Before executing on staging or production, verify the backup state per `docs/operations/backup-and-recovery.md`:

- A recoverable backup of the affected database exists and has been tested for restoration, not merely taken.
- For destructive steps, the data to be removed or re-interpreted is additionally **archived/exported** in a form that reconstructs the old representation if needed. Destructive steps never run against data whose pre-state cannot be reconstructed.
- Immutable historical data is not a backup concern for reconstruction in the usual sense — it must never be rewritten — but its integrity must be independently verifiable before and after the migration (see Verification below).

The principle: **the migration is reversible in the sense that the pre-migration state can be reconstructed, not in the sense that a destructive step will be mechanically undone.**

## Dry-Run on Staging

- Every migration set is rehearsed on staging against production-shaped data volume before it touches production (`docs/testing/test-environments.md`).
- The rehearsal runs the same commands, the same order, and the same verification queries that production will run.
- The rehearsal measures expected duration and data impact so production execution has a baseline to compare against. A production migration that runs far outside the rehearsal's expected envelope is an abort signal, not a surprise to absorb.
- The CI migration rehearsal step runs on every change that touches the schema: applying the migration set against a clean database and against a snapshot of the previous schema, verifying forward drift is empty and out-of-order/unreviewed migrations are rejected.

## Execution Order

Executions follow the strict order defined by the migration sequence and the release plan:

```text
1. Backup verified.
2. Expand step (schema) applied.
3. Code deploying the expand-compatible version applied.
4. Dual-write window opened where approved.
5. Backfill steps run (idempotent).
6. Verification queries run; cutover only if verification passes.
7. Cutover applied (reads flip to new representation).
8. Contract step applied only after no deployed code depends on the old representation.
9. Post-migration validation runs.
```

Migrations apply in strict linear order; a migration depends only on earlier migrations. Scheduled or parallel execution that could reorder the sequence is forbidden. The execution owner tracks each step to completion or to a declared abort before starting the next.

## Dual-Write Windows

When a dual-write window is required (approved exception):

- The window has a declared start and end condition, not a duration alone: it opens when both representations are writeable and closes when the verification queries prove the new representation is complete and correct.
- Within the window, every write goes to both representations; reads may use either as designed, but the two representations must not diverge.
- The window is closed (cutover) only after verification, and the old-representation path is retired only in the contract step.

## Data Backfill with Idempotency

Backfills are deterministic and idempotent: re-running a failed backfill must not double-apply or corrupt data. Concretely:

- The backfill derives each row's new value from authoritative, stable source state, not from changing counters or derived accumulators.
- The backfill is safe to restart from the beginning; its logic produces the same result on re-run.
- Backfills populate **non-immutable** data only. Backfills that would rewrite immutable rows are forbidden (they would reinterpret history: write-once results, locked dataset versions, published target/evaluator versions, executed experiment snapshots).
- Each backfill ships with its idempotency proof pattern and a verification query showing applied, skipped, and expected counts reconcile.

## Verification Queries

Every migration ships with verification queries run after each relevant step:

- **Schema verification**: the table/column/constraint exists with the expected definition; schema drift vs the migration sequence is empty.
- **Data verification**: counts reconcile (rows processed == rows expected), no NULLs where NOT NULL is required, referential integrity holds, and no immutable row changed identity or interpretation.
- **Integrity verification**: the invariants the schema enforces still hold — tenant isolation, evidence linkage (results cannot exist without evidence), immutability (a locked dataset still rejects writes), audit continuity.

Verification failing means: stop, do not cutover, do not proceed to the next step. The migration runs are recorded with their query results so the evidence trail of the migration itself is preserved.

## Post-Migration Validation

After the migration completes:

- Integration tests run against the migrated database to confirm application read/write paths still satisfy the invariants (tenant isolation, evidence linkage, immutability).
- The migrated schema is compared against the declared migration set; any drift is a blocking defect.
- The execution record is updated: what ran, what verified, what was skipped, who approved.
- If the change supports the Evidence Graph, confirm the new structures link to existing evidence without reinterpretation.

Post-migration validation failing after cutover is handled by the rollback protocol, never by silently reversing the migration (`docs/implementation/rollback-protocol.md`).

## How to Abort Safely Mid-Migration

A migration may be aborted safely only at defined points and only by the abort owner. Abort points:

- **Before the expand step**: abort is free; nothing changed.
- **After expand, before code deploy**: contract the just-added backstop only if it is additive, removable, and touches no immutable rows; otherwise complete the expand and proceed, because deployed code may already depend on it.
- **During backfill**: the backfill is idempotent; abort by stopping further processing and re-running later, never by partially unwinding it. The verification queries determine whether the partial state is safe to leave.
- **During dual-write**: abort by halting new work and reconciling the two representations to the authoritative one, then close the window. Never leave a dual-write window open on abort.
- **Never at a point where the contract step has begun**: the contract step is the point of no return for the old representation, and it runs only when nothing depends on the old representation anymore.

Abort rules:

1. **Stop writes to the migrating structures before attempting any reversal.** Writes being in flight while an abort reverses state is how data corruption happens.
2. Never reverse a destructive migration automatically. Reversal is a new forward migration or a documented exception, applied deliberately, per the rollback protocol.
3. Preserve whatever evidence the partial migration produced; aborted state is still audit-worthy.
4. Inform the defined communication list immediately; an aborted migration is a declared event with a post-mortem, not a quiet retry.

## The CI Migration Rehearsal Step

The CI migration rehearsal is non-negotiable for any change that touches the schema:

- Runs the migration set against a clean database (forward apply).
- Re-runs against a snapshot of the previous schema (no drift, backward-compatible path).
- Verifies the sequence is linear, ordered, and free of unreviewed additions.
- Verifies destructive steps are documented as reversible-to-state and immutable-safe.
- Fails the gate on out-of-order, unreviewed, or drift-producing migrations.

Rehearsal in CI is the floor; rehearsal on staging is the ceiling that production expectations are calibrated against.

## Related Documentation

- `docs/implementation/database-change-protocol.md` — how migrations are written and reviewed.
- `docs/implementation/rollback-protocol.md` — what happens when a release or migration must roll back.
- `docs/data/schema-evolution.md` — the expand/contract rules this protocol executes.
- `docs/data/immutability-rules.md` — the boundary that constrains what any migration step may do.
- `docs/operations/backup-and-recovery.md` — the backup and restoration obligations this protocol relies on.
- `docs/operations/incident-response.md` — the escalation path when an abort becomes an incident.
- `docs/testing/test-environments.md` — why staging rehearsal is calibrated to production shape.
- `docs/ci-cd` — the migration rehearsal and quality gates.