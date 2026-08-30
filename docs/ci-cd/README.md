# CI/CD

## Purpose

The CI/CD documentation describes how AEGIS changes move safely from a developer's editor to production. Its two governing goals are **preventing regression** and **making promotion repeatable**:

1. **Prevent regression.** Every change that merges must not make the AI systems AEGIS measures measurably worse — in quality, safety, reliability, or cost. The pipeline detects regressions before they reach production, and it verifies the change itself through the same non-compensatory gate discipline it applies to the AI under test.
2. **Make promotion repeatable.** A release is not a hand-run sequence of commands and screenshots. It is a deterministic pipeline that builds immutable artifacts, rehearses migrations, evaluates evidence, and records every gate verdict so the same promotion can be audited and reproduced.

## Pipeline Principle

The pipeline is built on **dependency-aware testing**: not every commit runs everything. Running the full evaluation suite on every commit is wasteful, slow, and expensive — LLM calls, provider invocations, and compute all cost money and time. CI selects tests by the changed components and the dependency graph, exactly as `grilling.md` specifies: a prompt change runs language and quality suites, a model change runs the regression suite, a retriever change runs the RAG suite, a tool schema change runs the agent and tool suites, a guardrail change runs the safety suite, and a memory policy change runs the memory suite. What runs on a given pull request is a function of what changed, not a constant "run everything."

Test tagging (`smoke`, `regression`, `safety`, `rag`, `agent`, `memory`, `expensive`) makes selection possible and is defined in `docs/testing/README.md`. The merge rules and the release gates that the pipeline enforces are specified in `docs/ci-cd/pull-request-gates.md` and `docs/ci-cd/release-policy.md`. A change is never complete until the mandatory checklist in `docs/implementation/definition-of-done.md` is satisfied with proof.

## Document Index

| Document | Description |
|---|---|
| [pipeline-architecture.md](pipeline-architecture.md) | The end-to-end pipeline from pull request to production, the dependency-aware test selection rule, and which stages are mandatory versus conditional per change. |
| [pull-request-gates.md](pull-request-gates.md) | The merge-blocking gates, which check implements each one, where it runs, and the concrete meaning of an unsafe migration. |
| [continuous-integration.md](continuous-integration.md) | The CI workflow details: per-PR stages, sharding, caching, reproducibility, dependency-aware selection, coverage enforcement, flaky-test policy, and artifact collection. |
| [continuous-delivery.md](continuous-delivery.md) | The delivery workflow: immutable artifact builds, staging deployment, E2E and migration rehearsal, and the controlled path to a release candidate. |
| [deployment-strategy.md](deployment-strategy.md) | How a release candidate is promoted: staged rollout, release-gate execution, deployment verification, and automatic rollback triggers. |
| [rollback-strategy.md](rollback-strategy.md) | Rollback in CI/CD: artifact, configuration, and feature-flag rollback, automatic versus manual triggers, migration interplay, and evidence safety. |
| [migration-strategy.md](migration-strategy.md) | How schema changes flow through CI to staging to production: expansion, backfill, contract, verification, and the immutability boundary. |
| [release-policy.md](release-policy.md) | What constitutes a release, versioning, cadence, release candidates and sign-off, the hotfix path, release notes, and the audit trail that ties each release to its evidence. |

## Related Documentation

- `docs/testing/` — the test pyramid, test tagging, dependency-aware selection policy, and quality gates that CI enforces.
- `docs/implementation/definition-of-done.md` — the completion checklist every change must satisfy before it is releasable.
- `docs/data/schema-evolution.md` and `docs/data/immutability-rules.md` — the migration and immutability boundaries that the pipeline enforces in stages and in production.
- `grilling.md` — the CI facts (dependency-aware test selection, composite and non-compensatory gates, service accounts for CI/CD) that this documentation operationalizes.
