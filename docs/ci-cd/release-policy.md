# Release Policy

## Purpose

The release policy defines what a release is, how one is produced, and how it is audited. A release is not a tag on a branch; it is an immutable artifact that satisfied the Definition of Done and the release gate, carries its migration bundle, and is paired with the evaluation evidence that allowed it to pass. No release without evidence.

## Versioning Scheme

Releases use a **semantic version** (major.minor.patch) applied to the immutable artifact:

- **Major** — a breaking interface or behavior change.
- **Minor** — an additive, backward-compatible change.
- **Patch** — a small, targeted fix (including the hotfix path).

Every release version maps to exactly one immutable artifact digest. The version and digest together are the release's identity and its provenance; the version label is never reused for a different digest.

## What Constitutes a Release

A candidate becomes a release only when **all** of the following hold:

- **Definition of Done satisfied** — the mandatory completion checklist in `docs/implementation/definition-of-done.md` is verified with proof.
- **Acceptance criteria pass** — the change satisfies its acceptance criteria (`docs/requirements/acceptance-criteria.md`).
- **Release gate passes** — the composite, non-compensatory gate is satisfied (quality, critical safety, p95 latency; `docs/ci-cd/deployment-strategy.md`).
- **Docs updated** — required documentation, including release notes, is current.
- **Artifact immutable** — the artifact is built once and its digest is frozen; the release is that digest.
- **Migration bundled** — any schema change ships as a bundled, rehearsed migration (`docs/ci-cd/migration-strategy.md`).

A release that fails any of these conditions is not released; it is a candidate that must return to the pipeline.

## Release Cadence

Releases follow a controlled cadence determined by the team (for example, a scheduled minor release window). Cadence is a discipline that keeps the promotion path rehearsed and reviewable; it is not a hard cap that forces an unverified release through. Urgent fixes use the hotfix path, not an unexamined break in the cadence.

## Release Candidates and Sign-Off

- A release candidate is a versioned, immutable artifact that has passed CI and staging (`docs/ci-cd/continuous-delivery.md`).
- Before promotion, the candidate is **reviewed and signed off**. Sign-off requires the gate verdicts to be recorded and the evidence to be attached; an approver signs the recorded verdict, not a blank approval.
- Promotion to production is a **controlled, authorized action** per `docs/ci-cd/deployment-strategy.md`, executed by an operator or release account with a service account.
- A candidate that fails sign-off, the gate, or post-deploy verification is not "released"; it is rolled back and either fixed forward or rejected.

## Hotfix Path

A hotfix is a small, targeted corrective release. It must:

- Contain only the minimal, targeted changes required for the fix.
- Run **the same gates** with the same pass criteria — risky checks are never waived for speed.
- Be **expedited** but not unverified: it takes a reduced-but-real validation path (a smaller artifact, a targeted regression and safety suite, and staging verification proportionate to scope) rather than the full minor-release review.
- Ship with its migration bundle if it touches the schema, and follow the same migration and rollback rules.

An expedited process compresses time and scope, never the quality or safety bar.

## Release Notes Requirement

Every release has release notes that describe:

- What changed, in user- and operator-meaningful terms.
- Any API or schema changes and their migration implications.
- Any behavior or threshold changes.
- Known limitations or follow-up work.

Release notes are required documentation and are validated before release; a release without required notes is not done.

## Audit and Evidence of Release

The release record is the audit trail of the promotion. It attaches, per release, the **gate verdicts and evidence** that permitted it:

- CI verdicts and artifacts (test reports, coverage, security scan, OpenAPI diff) per `docs/ci-cd/continuous-integration.md`.
- Staging verdicts (E2E, migration rehearsal, reliability evidence).
- The **release-gate verdict**: the composite policy evaluation and its normalized metric inputs.
- The **release↔evidence link**: for every gate that requires evidence, the evidence is recorded with the release — the evaluation results, evaluator and judge identity and version, dataset and target versions, and confidence that produced the pass (`docs/architecture/evidence-architecture.md`, `grilling.md` Q50).
- Sign-off records and the controlled deploy action.

This is what makes promotion repeatable and auditable: a future question "why was this released?" resolves to a recorded, evidence-backed verdict on an immutable artifact — not to memory.

## Release ↔ Evidence Link

The rule is absolute: **no release without evidence for the gates that require it.**

- The release gate's pass is only meaningful if the evaluation evidence behind each condition is attached: the quality score and its evaluator, the critical-safety-failure count and its safety evidence, the p95 latency and its measurement.
- Evidence is immutable; it is recorded once and never rewritten, per `docs/data/immutability-rules.md`. A release's evidence cannot be changed after the fact.
- A release whose required evidence is missing, non-reproducible, or from an uncalibrated evaluator is not a valid release, regardless of the branch state.

Because evidence attaches to the artifact and the gate verdict, and both are immutable, the release record is trustworthy provenance for the entire lifecycle of the release.

## Related Documentation

- `docs/ci-cd/continuous-delivery.md` — how a release candidate is built and proven.
- `docs/ci-cd/deployment-strategy.md` — the release gate and promotion.
- `docs/ci-cd/migration-strategy.md` — the bundled migration requirement.
- `docs/implementation/definition-of-done.md` — the completion prerequisite.
- `docs/architecture/evidence-architecture.md` — the evidence plane that links a release to its proof.
- `docs/data/immutability-rules.md` — why release evidence is immutable.
