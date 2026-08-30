# Rollback Strategy

## Purpose

Rollback is the controlled answer to a failed deployment. It is not an improvised scramble; it is a defined, exercised path that restores service while protecting evidence and obeying the migration and immutability rules. Every controlled deploy keeps a rollback path open before it starts.

## Rollback Types

CI/CD rollback takes one of three forms, used alone or together:

### Artifact Rollback

- Return the deployed service to a **previous immutable image**.
- The artifact's digest never changes after it is built (`docs/ci-cd/continuous-delivery.md`), so "the previous version" is a precise, reproducible thing — a known-good image, not "whatever was there."
- This is the default and fastest rollback; it is always possible because every release is an immutable image.

### Configuration Rollback

- Revert the configuration bundle to a previous versioned snapshot.
- Configuration is versioned with the artifact, so a config rollback points at a precise prior state, not a hand-edited guess.

### Feature Flag Off

- Disable the changed behavior behind a feature flag rather than reverting code or configuration.
- Used when the bad behavior is localized and can be contained rapidly without a full artifact or config revert.
- A feature flag off is temporary containment, not a substitute for a real fix; it is followed by artifact or configuration rollback and a proper corrective release.

## When Rollback Is Automatic vs Manual

### Automatic Rollback

Rollback is automatic when a deployment fails its defined verification in a way that is unambiguous and reversible without harm:

- **Release gate failure** — the deployed candidate violates a blocking gate condition after deploy (for example, a critical safety failure).
- **Critical alert** — an observability alert on availability, error rate, p95 latency, or a critical safety signal exceeds the configured threshold.

Automatic rollback is limited to artifact/configuration/feature-flag actions that are safe to reverse instantly: return to the known-good image, restore config, or flip a flag. Automatic rollback never runs a destructive migration reversal (see below).

### Manual Rollback

Rollback is manual when automation cannot safely decide:

- **Partial rollback** — only part of the deployment is bad, and an operator must determine the correct boundary of the revert without disturbing healthy components.
- **Data-related rollback** — the failure involves schema state, backfills, or data; an operator must decide against the migration and evidence rules, not a blind reverse.

## Interplay with Migrations

Rollback and migrations are tightly coupled, and the rule is absolute:

- **Never auto-run a destructive migration rollback.** Automation never reverses a destructive migration as a safety action.
- Migrations use **expand/contract and additive-first**: new columns and tables are added before anything that depends on them, so code can roll back to the previous image while leaving the expanded schema in place (`docs/data/schema-evolution.md`, `docs/ci-cd/migration-strategy.md`).
- **Rollback is the contracting leg**, not a blind reversal: remove the backstop only after the new code is fully replaced. A code rollback with a destructive migration already applied is handled by a **new forward migration** that corrects state, never an undocumented reversal, because a reversal could rewrite immutable rows or lose audit continuity.
- Destructive steps are written so old data can be reconstructed (archival export) before they execute; rollback does not destroy the ability to rebuild state.

Because schema changes are additive and released in the expand → deploy → backfill → contract order, the most common rollback is a pure **artifact rollback** that leaves the schema valid.

## Evidence Safety

Rollback must protect the evidence plane. The rule:

- **Rollback never deletes or rewrites immutable evidence or results.** Traces, executions, evaluator results, metric results, and gate verdicts are write-once and are not affected by a rollback (`docs/data/immutability-rules.md`).
- A rolled-back version's evaluation evidence remains valid and linked; rolling back does not falsify what was measured.
- **No score without evidence** still holds after a rollback: any post-rollback verification produces new evidence attached to the rolled-back artifact.

Rollback restores service and state; it never touches the audit trail.

## Post-Rollback Triage Flow

After a rollback, the team follows a systematic triage:

1. **Confirm service restored** — the known-good version is live and monitoring is clean.
2. **Verify evidence integrity** — confirm no immutable result, trace, or verdict was altered by the rollback and that the audit log is intact.
3. **Classify the failure** — map the rolled-back candidate's failure to its class (quality, safety, reliability, migration, or security) per the failure architecture.
4. **Record the incident** — log the trigger, the rollback action taken, and the evidence.
5. **Decide the corrective path** — produce a new forward artifact or migration, rehearse it in staging, and re-enter the pipeline; an unexamined re-deploy of the same thing is not an answer.
6. **Update runbooks** — feed the finding into the incident-response and rollback protocols so the next occurrence is faster and safer.

The operational details are in `docs/implementation/rollback-protocol.md` and the incident response in `docs/operations/incident-response.md`.

## Related Documentation

- `docs/ci-cd/deployment-strategy.md` — the rollout and verification that define when a rollback triggers.
- `docs/ci-cd/migration-strategy.md` — the expand/contract flow that makes artifact rollback safe.
- `docs/data/immutability-rules.md` — why rollback cannot touch immutable evidence or results.
- `docs/implementation/rollback-protocol.md` — the operational rollback runbook.
- `docs/operations/incident-response.md` — the incident handling the post-rollback flow feeds.
