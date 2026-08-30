# Pull Request Gates

## Purpose

The pull request gates define the conditions under which a change may **not** merge. They are the first line of regression prevention: a pull request that fails any gate is blocked until the failure is fixed, never merged and removed later with a follow-up. The gates are enforced automatically by the pipeline in the relevant stage and cannot be bypassed by a reviewer "approving anyway."

## The Merge-Blocking Gates

The pull request may not merge if **any** of the following is true:

```text
Formatting fails
Type checking fails
Unit tests fail
Required integration tests fail
Migration unsafe
API contract breaks
Security scan fails
Coverage decreases beyond policy
Architecture rules violated
Required documentation missing
```

Each gate, the check that implements it, and the stage where it runs are specified below.

## Gate: Formatting Fails

- **Check**: the formatter (per `docs/development/coding-standards.md`) reports a diff or failure.
- **Runs in**: static analysis stage (STATIC).
- **Notes**: formatting is deterministic and unnegotiable. A format failure means the change has not been normalized to the repository standard.

## Gate: Type Checking Fails

- **Check**: the static type checker reports errors.
- **Runs in**: static analysis stage (STATIC).
- **Notes**: type errors are caught before any runtime test, so they fail fast. Type checking runs on every PR, including docs changes that touch code-facing examples.

## Gate: Unit Tests Fail

- **Check**: the unit suite (`docs/testing/unit-testing.md`) reports any failure.
- **Runs in**: unit stage (UNIT).
- **Notes**: unit tests cover domain rules, policy evaluation, gate logic, retry classification, and evaluator logic in complete isolation. A failure here indicates a broken invariant, not flaky infrastructure.

## Gate: Required Integration Tests Fail

- **Check**: the dependency-selected integration set (`docs/testing/integration-testing.md`) reports a failure.
- **Runs in**: selective integration stage (INTEGRATION).
- **Notes**: only the integration suites affected by the change (directly or via the dependency graph) are required on the PR. A failure of a required integration test blocks the merge; the full integration catalog remains the responsibility of staging.

## Gate: Migration Unsafe

- **Check**: the migration gates run every migration against a clean database and against a snapshot of the previous schema (`docs/data/schema-evolution.md`, `docs/ci-cd/migration-strategy.md`).
- **Runs in**: selective integration stage (INTEGRATION), triggered whenever the database changed.
- **What "unsafe migration" means concretely**: a migration is unsafe when any of the following is true:
  - **Destructive without review** — the migration drops, renames, re-types, or reinterprets a column or table and was not reviewed and approved by an Owner/Admin/data steward (`docs/implementation/database-change-protocol.md`).
  - **Touches immutable tables** — the migration would rewrite or reinterpret immutable rows: historical results, locked dataset versions, published target or evaluator versions, or executed experiment snapshots (`docs/data/immutability-rules.md`). This is forbidden without exception.
  - **Missing up/down** — the migration is not a complete, ordered, forward-committed step with the correct up (and, for destructive steps, an archival/down that reconstructs state). An unreviewed, out-of-order, or irreversible migration fails the gate.
- **Notes**: CI rejects schema drift, out-of-order migrations, and any migration that violates the expand/contract and immutability rules before the schema reaches a shared environment.

## Gate: API Contract Breaks

- **Check**: contract tests pin every cross-boundary interface — API to client, worker to queue, worker to target adapter, adapter to evaluator, and webhooks (`docs/testing/contract-testing.md`).
- **Runs in**: contract stage (CONTRACT).
- **Notes**: a breaking change to a contract fails the PR gate and requires the API versioning policy (`docs/api/versioning-policy.md`). A breaking change is only legal as an additive version bump with a migration path, never a silent replacement.

## Gate: Security Scan Fails

- **Check**: the security scan — dependency and supply-chain scanning, plus the code-level security checks from `docs/testing/security-testing.md`.
- **Runs in**: security stage (SECURITY).
- **Notes**: the scan runs on every PR by default. A finding that introduces a known-vulnerable dependency, a secret, a tenant-isolation regression, or a PII redaction gap blocks the merge.

## Gate: Coverage Decreases Beyond Policy

- **Check**: the **coverage diff gate** compares the pull request's coverage against the merge base. It fails if coverage on the changed lines or the affected modules decreases beyond the configured policy threshold.
- **Runs in**: unit stage (UNIT), and re-checked in staging for the end-to-end path.
- **Notes**: coverage is enforced **diff-based**, not against an absolute evergreen target alone. The gate answers "did this change lower coverage," so a change that adds untested paths is blocked even if the global number is otherwise healthy. See `docs/ci-cd/continuous-integration.md`.

## Gate: Architecture Rules Violated

- **Check**: an **architecture-boundary lint** / dependency-rule enforcement that verifies the change respects the layer boundaries and dependency graph in `docs/development/dependency-rules.md` and the layer files in `docs/development/layers/`.
- **Runs in**: static analysis stage (STATIC).
- **Notes**: the rule is structural, not stylistic. Examples that fail: the domain layer importing an HTTP or SQL library, an interface-layer handler reaching directly into infrastructure, or an application-layer service depending on an interface-layer component. Circular dependencies and boundary violations fail the gate.

## Gate: Required Documentation Missing

- **Check**: the documentation rules validate that the change satisfies `docs/implementation/definition-of-done.md` and the repository's documentation requirements — release notes where applicable, API/`OpenAPI` updates where the API changed, migration documentation where the schema changed.
- **Runs in**: static analysis stage (STATIC) and the release gate (GATE).
- **Notes**: a feature that ships with broken, missing, or unreviewed required documentation is not done by the repository's own standard. A docs-only change runs docs validation; a code change also verifies that any required companion documentation exists.

## Non-Compensatory Application

The gates are **non-compensatory in aggregate but each gate is independently blocking**. A change that passes every gate except one cannot be "rescued" by being especially good on the others: a perfect quality suite does not excuse a failed security scan, a broken contract, or an unsafe migration. This mirrors the non-compensatory safety rule for AI evaluation (`grilling.md` Q497-498): a critical failure in any required dimension is a block regardless of improvements elsewhere.

## Related Documentation

- `docs/ci-cd/pipeline-architecture.md` — the pipeline in which these gates run and the mandatory-versus-conditional boundary.
- `docs/ci-cd/continuous-integration.md` — how static, unit, contract, security, and selective integration execute and report.
- `docs/ci-cd/migration-strategy.md` — the full migration flow the "migration unsafe" gate enforces.
- `docs/testing/README.md` — the test pyramid, tags, and quality gates these merge rules enforce.
- `docs/implementation/definition-of-done.md` — the completion checklist that underlies the documentation and coverage gates.
