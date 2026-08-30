# Continuous Integration

## Purpose

Continuous Integration (CI) verifies every pull request cheaply, quickly, and reproducibly before it merges, and it produces the evidence artifacts the rest of the pipeline consumes. CI is governed by dependency-aware testing: it runs what the change affects, not everything. The per-PR stages are described in `docs/ci-cd/pipeline-architecture.md`; the merge-blocking conditions they enforce are in `docs/ci-cd/pull-request-gates.md`.

## The Per-PR Pipeline

### Static (mandatory)

- Lint and type check.
- Format verification.
- Architecture-boundary / dependency-rule lint (`docs/development/layers/`, `docs/development/dependency-rules.md`).
- Docs validation (lint, link checks); a required-documentation check against `docs/implementation/definition-of-done.md`.

### Unit (mandatory)

- The fast unit suite in complete isolation from infrastructure and models (`docs/testing/unit-testing.md`).
- Coverage computation for the coverage-diff gate (`docs/testing/README.md`).

### Contract (mandatory on code PRs)

- Contract tests pin every cross-boundary interface: API to client, worker to queue, worker to target adapter, adapter to evaluator, and webhooks (`docs/testing/contract-testing.md`).
- An `OpenAPI` diff is generated on API changes to drive the API versioning policy (`docs/api/versioning-policy.md`).

### Security Scan (mandatory)

- Dependency and supply-chain scanning.
- Code-level security checks: secrets detection, PII redaction coverage, tenant-isolation regressions (`docs/testing/security-testing.md`).

### Selective Integration (conditional)

- Only the integration suites affected by the change, selected by affected-paths plus the dependency graph, run against real contained PostgreSQL and Redis.
- The full integration catalog remains the responsibility of staging (`docs/testing/test-environments.md`).

## Test Sharding and Parallelization

The unit, contract, and selective-integration suites are **sharded** so a pull request returns fast. Key properties:

- **Shard determinism**: tests are assigned to shards by a stable hash of their identifier, so a given code revision always maps tests to the same shards. Results are reproducible across retries.
- **Order independence**: no test depends on another test's execution to pass; sharding never changes pass/fail semantics.
- **Parallelism with bounded cost**: the number of shards and worker concurrency are capped per project and budget, so parallelizing a pull request cannot silently multiply AI spend or billable time.

The `expensive` tag never shards per commit; expensive suites are scheduled and budgeted separately (`docs/testing/test-environments.md`).

## Caching

- **Build cache** for compiled or built artifacts keyed by the dependency lock file and toolchain version, so unchanged dependencies are not rebuilt.
- **Dependency cache** for the toolchain and third-party packages, keyed by the locked dependency manifest.
- **Evaluation/cache reuse** where explicitly allowed: identical inputs and evaluator configuration reuse cached evaluations (`grilling.md` Q172). Caching is invalidated on evaluator-prompt or model-version change (`grilling.md` Q173-174).
- **Cache safety**: caches never mask a failed build or test. A cache hit is only trusted when the key is derived from content that guarantees equivalence.

## Reproducibility of CI

CI runs with a **locked toolchain**. The language runtime, package versions, formatter, linter, type checker, and build tools are pinned in lock files and in the CI image. There are no floating version ranges in CI, per `docs/development/dependency-rules.md`. Reproducibility guarantees:

- The same commit always produces the same lint/type/unit/contract/security outcomes.
- An artifact is a deterministic function of its source and toolchain, so the image digest is meaningful provenance.
- A build that cannot be reproduced from a locked toolchain is an incident, not an excuse.

## Fast Feedback Targets

The pipeline is ordered so the cheapest, most informative checks run first:

1. Formatting and type errors fail within the first minutes.
2. Architecture and docs violations fail next, before any expensive runtime work.
3. Unit tests and the coverage-diff gate follow.
4. Contract tests and the security scan run after the shape of the change is known.
5. Selective integration runs last among PR stages, since it is the most expensive per-PR stage.

Time to feedback on a typical code change is minutes, not hours; a change almost never reaches selective integration with a formatting or type error still present.

## Dependency-Aware Selection

Selection decides which suites run on a given pull request:

- **Affected paths** map changed files to components (API, evaluator, schema, documentation, security policy, and so on).
- **Dependency graph** (`docs/development/dependency-rules.md`, `docs/development/layers/`) propagates a change to every component that depends on it, so dependent tests run even when their own files did not change.
- **Tag mapping** (`docs/testing/README.md`) routes the change to the correct suites: prompt goes to language and quality, model to regression, retriever to RAG, tool schema to agent and tool, guardrail to safety, memory policy to memory.
- The selection is deterministic and recorded in the CI report, so it is auditable which suites a change did — or deliberately did not — run.

## Coverage Enforcement (Diff-Based)

Coverage is enforced as a **coverage-diff gate**, not an absolute number alone:

- The gate compares the pull request's coverage of the changed lines and affected modules against the merge base.
- A change that lowers coverage beyond the configured policy threshold fails the gate, even if the global coverage number is healthy.
- The diff basis prevents a large, untested change from passing by leaning on the coverage accumulated by unrelated code.

The exact threshold is policy-configurable; the mechanism (diff-based, merge-base comparison) is fixed so the rule cannot be silently weakened by re-baselining to a worse number.

## Flaky-Test Policy

A flaky test is a real problem, not a nuisance. The policy:

- **Tag, do not silently disable.** A flaky test is tagged `flaky` so it is visible and tracked. It is quarantined — excluded from gating — only after the flake is reproduced and documented, never by deleting the test or turning it off without a record.
- **Quarantine is temporary and counted.** A quarantined test is tracked and must be fixed or removed within a documented window; quarantined tests cannot accumulate indefinitely.
- **A flaky gate does not mask a regression.** A metric or test that wobbles under repeated evaluation is a candidate for flakiness analysis, not a permanent bypass (`grilling.md` Q243); blocking is reserved for stable, meaningful checks (`docs/testing/testing-strategy.md`).
- **Flakiness is itself reported.** Repeated-evaluation variance is captured so the team knows which checks are reliable and which are noisy.

## Artifact Collection

Every CI run collects the artifacts the rest of the pipeline and the audit trail depend on:

- **Test reports** — per-suite pass/fail and timing, retained for the run.
- **Coverage reports** — the diff-based coverage delta against the merge base.
- **Logs** — build, test, and security-scan logs, retained for troubleshooting and audit.
- **OpenAPI diff** — the generated interface delta for API changes, driving the versioning policy review.
- **Selection and verdict records** — which suites ran, why, and each gate verdict, forming the evidence that attaches to the release record per `docs/ci-cd/release-policy.md`.

Artifacts are stored immutably and keyed by the commit and the pipeline run, so a release can always be traced back to its CI evidence.

## Relation to the Rest of the Pipeline

- The PR gates in `docs/ci-cd/pull-request-gates.md` consume CI outcomes.
- The immutable artifact CI builds feeds `docs/ci-cd/continuous-delivery.md`.
- The coverage and quality evidence feed the release gate in `docs/ci-cd/deployment-strategy.md`.
