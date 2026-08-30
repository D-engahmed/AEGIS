# Continuous Delivery

## Purpose

Continuous Delivery turns a passing, merged change into a deployable artifact and validates that artifact in staging before it becomes a release candidate for production. Delivery is deliberate: it builds once, verifies in a production-shaped environment, and only then exposes a release candidate to the controlled promotion path described in `docs/ci-cd/deployment-strategy.md`.

Delivery is not "merge to production." The pipeline separates *integration* (the change is safe to merge) from *delivery* (an immutable artifact is built and proven in staging) from *deployment* (the release candidate is promoted to production on policy).

## Building Immutable Artifacts

On the `main` branch, CI builds a single, versioned, **immutable artifact**:

- **Versioned images** with a content-addressed digest and a semantic version label.
- **Bundled configuration**, versioned with the artifact and reviewed as part of the release.
- **Bundled migrations**, shipped with the artifact so the schema and the code that depends on it deploy together, in the order defined by `docs/data/schema-evolution.md` and `docs/ci-cd/migration-strategy.md`.

The artifact is immutable: its digest never changes after it is built, and a change to source produces a new artifact, never a mutation of an old one. Immutability is what makes the artifact trustworthy provenance for a release and what makes rollback to a previous image safe (`docs/ci-cd/rollback-strategy.md`).

## Automatic Deploy to Staging

Every artifact built from `main` is automatically deployed to **staging**. Staging is the environment that models production topology and data volume closely enough that results transfer (`docs/testing/test-environments.md`).

### E2E and Migration Rehearsal in Staging

- **E2E tests** run the full scenarios through every plane against the staged artifact and recorded or fake external responses (`docs/testing/end-to-end-testing.md`).
- **Migration rehearsal** applies the artifact's bundled migration set to production-shaped data before it ever touches production. This proves the migration expands, backfills, contracts, and verifies correctly under realistic conditions (`docs/ci-cd/migration-strategy.md`).
- **Integration, stress, load, soak, and chaos** suites run in staging where destructive testing is safe and never against shared or production data.

Staging is the gate that separates "the artifact built" from "the artifact is worth promoting." An artifact that fails staging does not advance.

## The Release Candidate

Once an artifact passes staging — E2E, migration rehearsal, and the applicable integration and reliability suites — it becomes a **release candidate** eligible for production promotion. The release candidate carries its immutable digest, its bundled migrations, and the accumulated evidence from CI and staging.

From this point the candidate moves toward production **on policy**, not by default. The promotion is governed by `docs/ci-cd/deployment-strategy.md` and `docs/ci-cd/release-policy.md`:

- The release gate evaluates the candidate's evidence against the composite, non-compensatory policy.
- The candidate is reviewed per the release sign-off rules.
- Deploy is triggered manually and controllably by an authorized operator with a service account, never automatically upon merge.

## Environment Promotion (Staging → Production)

Promotion is always the same, auditable sequence:

1. **Candidate frozen.** The release candidate's digest, configuration, and migrations are frozen and recorded.
2. **Staging verified.** The candidate has passing E2E, migration rehearsal, and reliability evidence from staging.
3. **Release gate evaluated.** The composite, non-compensatory gate is run against the candidate's evaluation evidence.
4. **Controlled deploy.** An authorized operator triggers the deploy of the identical immutable artifact to production.
5. **Production verified.** Post-deploy smoke suites and monitoring confirm the candidate behaves in production before it is treated as settled.

Each step records a verdict and attaches its evidence, so a promotion is always repeatable and auditable. There is no step that is a human "eye-ball it and ship"; even the review is recorded, and the deploy is an explicit, authorized action.

## How Deploy Is Triggered

The deploy is **manual and controlled**, not "merge to production":

- Only an authorized operator or release account initiates a production deploy.
- The deploy target is always an immutable artifact already proven in staging; nothing is built at deploy time.
- The bundle (image, config, migrations) is applied as a unit so the schema and code cannot drift apart.
- Phase `Production` verifies the deploy with smoke and monitoring before the pipeline considers it complete; a failed verification triggers rollback per `docs/ci-cd/rollback-strategy.md`.

The same rules apply to hotfixes and urgent changes: they take a smaller, targeted artifact, but they still build once, verify in staging (or an equivalent reduced validation per `docs/ci-cd/release-policy.md`), and deploy under the same controlled trigger. Expedited does not mean unverified.

## Related Documentation

- `docs/ci-cd/deployment-strategy.md` — the deployment strategy advice and the promotion decision.
- `docs/ci-cd/release-policy.md` — what makes an artifact a release, candidate sign-off, and the audit trail.
- `docs/ci-cd/migration-strategy.md` — how the bundled migrations flow through staging to production.
- `docs/ci-cd/rollback-strategy.md` — the rollback path that a controlled deploy keeps available.
- `docs/testing/test-environments.md` — the staging environment and the parity and cost rules that make its evidence transferable.
