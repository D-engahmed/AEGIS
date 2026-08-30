# Implementation Documentation

This folder is the **"how we implement"** half of the AEGIS documentation. It does not restate requirements and it does not re-draw the architecture. It answers one question for every change: **how do we change the system safely, in what order, with what discipline, and when is a change actually complete?**

The three documentation halves divide responsibility deliberately:

| Half | Location | Answers |
|---|---|---|
| Requirements | `docs/requirements/` | **WHAT** we build. Functional requirements, non-functional requirements, assumptions, and acceptance criteria. A change exists to satisfy some requirement. |
| Architecture | `docs/architecture/` | **WHERE and BOUNDARIES.** The planes, the layers, the module boundaries, the ADRs, and the invariants that structure the system. A change must respect these boundaries. |
| Implementation | `docs/implementation/` | **HOW TO CHANGE safely.** The order to build in, the workflow every agent follows, the protocols for features, database changes, API changes, migrations, rollbacks, and the Definition of Done. |

The implementation documents are the operative contract for anyone doing work in this repository. The requirements tell you what is legal to build; the architecture tells you where it may live; these documents tell you the steps that separate "I wrote code" from "the feature is done and safe."

## Cardinal Rule

**Nothing is complete until the Definition of Done is satisfied.**

A feature that compiles but fails its acceptance criteria is not done. A migration that applies but was never reviewed is not done. An API change that works in the dashboard but breaks the worker contract is not done. The Definition of Done is the single gate that turns implementation work into a shippable, trustworthy change, and an item in that checklist is done only when a file or tool test proves it. "It works on my machine" is never the proof.

## Document Index

| Document | Purpose |
|---|---|
| [`implementation-order.md`](implementation-order.md) | The recommended build order: phases, deliverables, tests, and the gates that must pass before the next phase starts. |
| [`agent-implementation-guide.md`](agent-implementation-guide.md) | The contract for any coding agent (AI or human): the workflow, how to read a task, how to pick a layer, when to propose an ADR, and how to verify work locally. |
| [`feature-implementation-protocol.md`](feature-implementation-protocol.md) | The 14-step protocol for implementing any feature, with a "how" and an "exit condition" for each step. |
| [`database-change-protocol.md`](database-change-protocol.md) | The mandatory process for every schema change: migrations, additive vs destructive classification, immutability boundaries, and test gates. |
| [`api-change-protocol.md`](api-change-protocol.md) | The process for changing the public API: additive vs breaking, contract tests first, OpenAPI, deprecation, and consumer impact tracing. |
| [`migration-protocol.md`](migration-protocol.md) | The operational runbook for applying data migrations during a release: backups, dry-run, execution order, backfill, verification, and safe abort. |
| [`rollback-protocol.md`](rollback-protocol.md) | The rollback runbook: trigger conditions, code vs migration rollback, data reversal rules, evidence preservation, and post-rollback analysis. |
| [`definition-of-done.md`](definition-of-done.md) | The mandatory completion checklist, how each item is verified, who signs off, and the proof rule. |

## How to Use This Folder

1. Read `agent-implementation-guide.md` before writing any code.
2. When starting a feature, follow `feature-implementation-protocol.md` step by step.
3. If the change touches the schema, additionally follow `database-change-protocol.md` and `migration-protocol.md`.
4. If the change touches the API, additionally follow `api-change-protocol.md` and the API impact list (`docs/api/versioning-policy.md`).
5. Before a release, rehearse migrations (`migration-protocol.md`) and know the rollback path (`rollback-protocol.md`) before it is needed.
6. Never mark a change complete until every checkbox in `definition-of-done.md` is verified with proof.

## Related Documentation

- `docs/development/agent-development-protocol.md` — the agent workflow this folder extends with implementation detail.
- `docs/development/layers/` — the layer files that tell you where a change belongs.
- `docs/data/schema-evolution.md` — the schema-evolution rules that `database-change-protocol.md` operationalizes.
- `docs/api/versioning-policy.md` — the API versioning rules that `api-change-protocol.md` operationalizes.
- `docs/requirements/acceptance-criteria.md` — the acceptance-criteria template that `definition-of-done.md` depends on.
- `grilling.md` — the product facts (immutability, evidence, bounded retries, MVP ordering) that these protocols enforce.
- `README.md` — the phase plan that `implementation-order.md` turns into build gates.