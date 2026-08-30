# Test Environments

## Purpose

Different test classes have different requirements: speed, fidelity, safety, and cost. Running a test class in the wrong environment is either useless (a container that does not resemble production), dangerous (chaos against real data), or wasteful (expensive suites on every commit). The environment tiers define what runs where, what each tier guarantees, and how the tiers are governed.

## Environment Tiers

### Local Development

- Runs **unit tests** and **fast integration tests** with containers (PostgreSQL, Redis) managed by the local harness.
- **No real provider**: targets and models are recorded fixtures or fake providers.
- Purpose: rapid feedback; a developer must be able to run the fast suite before pushing.
- Local environments never point at shared, staging, or production infrastructure, and never at a real tenant's data.

### CI Sandbox

- Runs the **per-PR gates**: static analysis, unit, contract, and security scans.
- Runs **selective integration** — the fast integration set, with real contained PostgreSQL and Redis — but not the full integration catalog.
- Purpose: gate every change quickly and at low cost; catch contract breaks, coverage drops, and security findings before a change merges.
- The gate set is defined in `docs/ci-cd/pull-request-gates.md`. Expensive suites (`expensive` tag) are not run per PR.

### Staging

- Runs **integration**, **end-to-end**, **stress**, **load**, **soak**, **chaos**, and **migration rehearsal**.
- Staging models production topology and data volume closely enough that results transfer: same component processes, same queue, same storage layout, representative dataset sizes.
- Chaos and destructive suites run here — never against shared or production data.
- Migration rehearsal proves the migration set against production-shaped data before it touches production.

### Production

- Runs **smoke suites** after deployment.
- Runs **monitoring and alerts**: synthetic transactions, health checks, availability, and reliability monitoring per the NFRs.
- Runs **canary evaluation**: a small, explicitly authorized evaluation slice against a deployed target version to confirm production behavior.
- Runs **no destructive tests**: no chaos, no stress, no red-team payloads, no test that mutates production state or triggers real side effects.

## Parity Rules

- Staging must match production in topology, runtime configuration, and data volume within documented tolerances; a load or chaos result is only meaningful relative to a staging environment that resembles production.
- The same migration set, schema, and configuration are exercised in local, CI, and staging; a tier that cannot run the migration set is not a testing environment for schema changes.
- Provider behavior in CI and local is recorded fixtures; staging may use real providers only in explicitly authorized, tagged suites, and production never runs provider-dependent tests outside canary evaluation.

## Environment Access Control

- Chaos, stress, and red-team workloads are restricted: only authorized operators may execute destructive suites, and their targets are synthetic scoped tenants.
- Red-team data and adversarial payloads are restricted to authorized personnel; dangerous payloads and sensitive application details are not broadly readable.
- Raw traces and evaluation data are authorization-gated in every tier; test environments enforce the same permission model as production so isolation bugs cannot hide behind "it is only a test environment."
- Access to production test actions (smoke, canary) is limited to deployment identities with explicit authorization.

## Cleanup and Isolation Per Tenant

- Every test tier runs per-tenant isolation: tests create their own organizations and projects, and a cross-tenant assertion must fail at every layer.
- Test data is cleaned up after runs; chaos workloads and stress datasets are removed from staging after verification.
- Isolation is tested between tenants, not only between test classes. A chaos run in tenant A must never affect tenant B or shared evidence.
- Shared staging is quarantined per run where needed so scheduled suites cannot corrupt each other.

## Cost Governance for Expensive Suites

Expensive suites (stress, load, soak, chaos, heavy evaluation) consume significant compute, AI spend, and time. Cost governance requires:

- Expensive suites are tagged `expensive` and run on schedules, never implicitly on every commit.
- Per-environment budgets cap how much load, chaos, or AI spend a scheduled suite can consume; exceeding the budget aborts the run and reports it.
- Cost per run is measured (target cost separated from evaluator cost), so suite cost is a reported number, not a surprise.
- The schedules and budgets are verified in the CI/CD gates rather than left to convention.