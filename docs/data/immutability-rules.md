# Immutability Rules

This document is the single source of truth for immutability in AEGIS. It defines the verbatim list of immutable resources, what makes each one immutable, how immutability is enforced, what a user can do instead of changing one, and the reason the rule exists. It is the data-layer authority that `docs/architecture/write-architecture.md` (Write Invariants) and `docs/data/schema-evolution.md` both reference.

## The Verbatim Immutables

This list is authoritative. These resources are immutable after creation or lock:

```text
Target Versions
Dataset Versions after lock
Experiment snapshots
Evaluator Versions
Historical Results
```

For each one: what makes it immutable, how lock/immutability is enforced, what the user can do instead, and the reason.

## Target Versions

**What makes it immutable.** A Target Version is a reproducible snapshot of the AI system's configuration: model, provider, prompt, tools, retrieval configuration, memory policy, guardrails, runtime configuration, and build identity (code commit, image digest). If any of these changed after version creation, historical experiments that referenced that version would no longer describe what actually ran.

**How immutability is enforced.** Once a target version is referenced by an experiment, it is immutable (`write-architecture.md` Target Version Immutability). Update and delete operations on referenced versions are rejected by the application service.

**What the user does instead.** Change the target and publish a **new target version**. Regression testing compares across versions (`v0.3` vs `v0.4`); it never rewrites `v0.3`.

**Reason.** Otherwise old experiments silently change meaning and regression signals become meaningless.

## Dataset Versions after lock

**What makes it immutable.** A Dataset Version is a snapshot of evaluation scenarios (test cases). Locking is a one-way operation that freezes the version so it can be referenced by experiments and produce reproducible results.

**How immutability is enforced.** Locking is irreversible. An unlocked draft may be modified freely; a locked version may not be modified or deleted (`write-architecture.md` Dataset Version Immutability; `data-lifecycle.md`). Constraints and application enforcement reject update/delete on locked versions.

**What the user does instead.** Edit the unlocked draft before locking, or create a **new dataset version** by branching/locking a fresh snapshot.

**Reason.** A locked dataset version is the reproducible input to experiments. Rewriting it would change the meaning of every experiment and score computed against it.

## Experiment snapshots

**What makes it immutable.** Running and historical experiments are immutable snapshots of the full evaluation configuration (target reference, dataset reference, evaluators, policies, environment, seed, settings).

**How immutability is enforced.** Once execution begins, the snapshot is immutable. Update operations are rejected; there is no path to rewrite a running or historical experiment (`write-architecture.md` Experiment Immutability; grilling.md Q153).

**What the user does instead.** **Clone** the experiment to create a new variant for controlled comparison. The original remains untouched.

**Reason.** Results must be explainable by their configuration (grilling.md Q175). If the configuration could change after the fact, the results would no longer be reproducible or explainable.

## Evaluator Versions

**What makes it immutable.** An Evaluator Version captures the evaluator code/plugin, configuration, judge model, and judge prompt version at a point in time. An evaluator is itself a versioned AI dependency (grilling.md Q222, Q250).

**How immutability is enforced.** Once versioned, the evaluator values are immutable; changes produce a new version (`write-architecture.md` Evaluator Version Immutability). This means a judge-model or judge-prompt change never invalidates historical comparison — it creates a new evaluator version instead.

**What the user does instead.** Change the evaluator and publish a **new evaluator version**.

**Reason.** Judge-model and judge-prompt changes would otherwise make scores from different judge configurations indistinguishable and non-comparable.

## Historical Results

**What makes it immutable.** Historical results (metric results and gate verdicts) are the terminal scores and outcomes of evaluations. They carry complete provenance and are written once.

**How immutability is enforced.** Results are write-once. There is no update or delete path for result rows in the schema (`database-design.md`); the Result Invariants require every result to reference its full upstream chain (`write-architecture.md`). Retries are idempotent and can never rewrite an existing result.

**What the user does instead.** Re-run an experiment to produce a **new** result; compare the new result against the historical baseline. Never alter the historical one.

**Reason.** "No score without evidence" implies the score must stay attached to the evidence that produced it, forever. Altering a historical result would falsify the evidence-based verdict.

## Additional Write-Once and Immutable Classes

Beyond the five verbatim immutables:

- **Execution records are write-once.** A terminal execution (succeeded, failed, cancelled) is never mutated to rewrite history. Failed and cancelled executions preserve the partial evidence they collected (`data-lifecycle.md`).
- **Metric results are write-once.** A metric result is computed, written once with full provenance, and never updated or deleted.
- **Evidence and artifacts are immutable.** Traces, executions, evaluator results, and evidence references are written once and never updated. There is no update path for evidence records (`evidence-architecture.md`).
- **The audit log is append-only.** Audit entries are never updated or deleted (`write-architecture.md` Audit Trail; `data-lifecycle.md`).

## Enforcement

Immutability is enforced at three layers, in depth:

1. **Database constraints/triggers where possible.** Unique execution IDs reject duplicate execution records. Check constraints and immutable-version semantics at the database layer reject unlawful updates before they can corrupt state. The schema simply does not include update/delete paths for immutable records (`database-design.md`).
2. **Application-layer enforcement.** The application service enforces immutability within the transaction boundary: update and delete operations on immutable resources are rejected with an error. Optimistic locking verifies an immutable resource has not changed between read and write (`write-architecture.md` Concurrency Control). This is the primary enforcement point.
3. **Retry/idempotency guarantees that never rewrite immutables.** Idempotency keys ensure retried operations create at most one immutable record and never re-run an operation over one. Unique IDs plus idempotency prevent duplicate writes and forbid rewriting an existing immutable.

Immutability is therefore not a convention — it is enforced by the schema, the write pipeline, and concurrency controls together, and it is a security property (a disguised attacker cannot falsify historical verdicts; `data-ownership.md`).

## The Migration Boundary

**If a migration would touch an immutable row, it is forbidden.** Schema evolution never rewrites historical results, locked dataset versions, published target/evaluator versions, or executed experiment snapshots to a new interpretation. If a column must change meaning or type, the correct action is to **create a new version entity** that carries the new definition, leaving the immutable ones untouched. See `schema-evolution.md`.

## Related Documentation

- `docs/architecture/write-architecture.md` — the Write Invariants and concurrency controls that enforce these rules.
- `docs/architecture/evidence-architecture.md` — the Evidence Plane's immutability guarantees.
- `docs/data/data-lifecycle.md` — how immutability manifests across the lifecycles of each data class.
- `docs/data/schema-evolution.md` — the migration boundary that immutability imposes.
- `docs/data/database-design.md` — how the schema (or absence of update/delete paths) encodes immutability.
