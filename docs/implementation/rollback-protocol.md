# Rollback Protocol

## Purpose

This document defines when and how AEGIS rolls back. Rollback is the escape hatch for a release that must not stand: a failed gate, an observability alert, or an incident. It is written so that the rollback itself never damages the evidence chain: rolling back code is routine, rolling back a migration is constrained, and rolling back data is governed by immutability.

The governing truths from the product facts:

```text
Migrating immutable data backward is forbidden.
Rollback stops writes BEFORE attempting any data reversal.
Preserve evidence. Partial evidence is preserved, never deleted.
```

## Trigger Conditions

Rollback is triggered by any of the following, evaluated against the release's declared expectations:

- **Release gate failure.** A deployment gate that was expected to pass fails: task success below threshold, critical safety failures present, latency or cost thresholds breached (grilling.md Q490-Q499). A release already behind a blocked gate does not advance; it rolls back the change that moved it backward.
- **Observability alerts.** Production monitoring or synthetic checks degrade against the baseline: availability, error rate, latency envelopes, cost anomaly, or reliability metrics (`docs/development/layers/10-observability-layer.md`).
- **Incident.** A security or reliability incident is declared per `docs/operations/incident-response.md`, and the released change is implicated or plausibly implicated.

The trigger decision is made by the on-call/incident owner using the evidence available, not by a guess. If the alert shows the system degrading and no investigation yet, roll back first if the release window is narrow, per the escalation rules in the incident-response runbook. Rolling back early and correctly beats investigating with a broken system.

## Rollback Types

### Code Rollback

The default and preferred rollback: deploy the **previous artifact** (the last known-good build) through the standard deploy path.

- Code rollback is safe whenever the schema supports it. That is why schema changes use expand/contract: during expand, the previous code remains compatible, so rolling back code is a deploy, not a data operation.
- Rollback the code first when a migration accompanies the release. If the schema is still in the expand phase, the previous artifact runs against the expanded schema without incident.
- Code rollback restores the previous behavior; it does not undo any data that the failed release wrote. Writes made by the failed release remain, which is acceptable and auditable.

### Migration Rollback — Cautions

```text
Never run a destructive migration rollback automatically.
```

Migrations are forward-committed. A schema-change release rolls back as follows:

- **During expand / before the new code took over**: roll back the code to the previous artifact; the expanded schema stays (it is backward compatible). The contract step is deferred until the release is healthy again.
- **After a destructive migration step ran and the release must retreat**: a destructive migration is **not** automatically reversed. The correct action is a new forward migration that corrects state, applied deliberately, or a documented exception under human approval. Automatic replays of `down` migrations in production are forbidden because they can rewrite immutable rows and lose audit continuity.
- **An aborted migration during the release** follows `docs/implementation/migration-protocol.md` abort rules: stop writes, reconcile, preserve state. It does not invoke a blind schema reversal.

### Data Rollback Rules — Destructive vs Additive

| Migration class | Rollback behavior |
|---|---|
| **Additive** | Contract the added backstop only after no deployed code depends on it (expand/contract contracting leg). Additive columns/tables can be dropped after the code that needs them is gone, as long as doing so touches no immutable rows and the removal itself is a migration. |
| **Destructive** | Never automatically reversed. The pre-destructive state was archived before execution; reconstruction to that state, if ever required, is a deliberate, reviewed forward migration using the archive, and it never rewrites immutable rows. In practice the forward-fix migration is the rollback mechanism. |
| **Immutable data** | Backward migration of immutable data is **forbidden**. Historical results, locked dataset versions, published target/evaluator versions, and executed experiment snapshots are never moved backward, re-interpreted, or deleted to service a rollback. |

## Evidence Preservation

Rollback must never delete evidence.

```text
Partial evidence is preserved. A failed or cancelled execution keeps the
evidence it collected. A rollback that discards traces, results, or audit
entries is itself an incident.
```

Concretely:

- Traces, executions, metric results, gate verdicts, and audit entries written by a rolled-back release remain. They are evidence of what the release did, including its failures.
- Rollback stops **new** writes of the failing behavior (by restoring the previous artifact and stopping the release's writes before any data reversal) but never deletes the writes that already happened.
- Evidence from before and during the failed release stays linked per the Evidence Graph; a rollback does not re-interpret old evidence to look better.
- If the rollback's own actions must be recorded, they are recorded in the audit log — rollback is not an exception to auditability; it is an auditable event.

## The Rollback Sequence

```text
1. Stop writes BEFORE attempting data reversal.
   Freeze or divert the failing write path, restore the previous code artifact,
   and only then consider any data change.

2. Restore the previous artifact (code rollback).

3. Stabilize: confirm the system returns to its baseline via the verification
   queries and integration tests that defined the pre-release state.

4. Reassess data: if schema work accompanied the release, apply the migration
   rules above. Never reverse a destructive migration automatically. Using
   migrations as forward fixes, never blind reversals, is the rule.

5. Preserve evidence: no traces, results, or audit entries are deleted.

6. Communicate: notify users/subscribers per the communication plan.

7. Analyze: feed the post-rollback analysis into the incident response.
```

## Communication to Users

Rolled-back behavior affects consumers. Communication happens through the platform's own mechanisms:

- **Webhooks**: subscribers receive the events their contracts define for run/verdict outcomes, so a consumer whose pipeline was gated by the failing release learns of the state change through the channel they already consume (`docs/api/webhooks.md`).
- **Alerts**: the observability alerting path declares the rollback event and its reason (`docs/development/layers/10-observability-layer.md`).
- **Release/changelog notes**: the release record is updated to show the rollback, its trigger, and the evidence.

Communication must not claim a rollback "restored correct data" when the evidence says otherwise. The message states what was rolled back, what data was preserved, and what is under investigation.

## Post-Rollback Analysis

Every rollback produces a post-rollback analysis that feeds `docs/operations/incident-response.md`:

- What triggered the rollback (gate, alert, incident) and the evidence.
- Where the failure originated: requirement, implementation, migration, API contract, or gate configuration.
- Which rolls back types were used and whether evidence integrity was preserved.
- What forward fixes are required, including any new migration or contract change.
- What the rollback taught about the process: was the gate wrong, the migration under-rehearsed, the contract under-traced?

The analysis is written into the incident record; the rollback is not closed until the analysis records the evidence chain survived intact.

## Related Documentation

- `docs/implementation/migration-protocol.md` — the migration runbook and abort rules this protocol assumes.
- `docs/implementation/database-change-protocol.md` — why migrations are forward-committed and never blindly reversed.
- `docs/data/schema-evolution.md` — the expand/contract posture that makes code rollback safe.
- `docs/data/immutability-rules.md` — why migrating immutable data backward is forbidden.
- `docs/operations/backup-and-recovery.md` — the restore/archive foundation for any data reconstruction.
- `docs/operations/incident-response.md` — the incident flow the post-rollback analysis feeds.
- `docs/api/webhooks.md` — webhook event delivery used for rollback communication.
- `docs/ci-cd/pull-request-gates.md` — the gates whose failure triggers a rollback.