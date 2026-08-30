# API Documentation

This directory is the authoritative description of the AEGIS public API: how clients authenticate, how resources are exposed, how operations behave, how failures are reported, and how the contract evolves. The API is the primary integration surface for AEGIS. Everything a client can observe or drive through the web dashboard is available through the API, and the API is the contract that SDKs, CLI tooling, CI/CD pipelines, and service accounts build against.

The API documentation assumes the product model described in `README.md`, the requirements in `docs/requirements/`, and the architecture contracts in `docs/architecture/` (particularly the read, write, security, execution, and failure architecture). Before reading the API documents, read those sources so that the vocabulary and invariants used here are unambiguous.

## What the API Is

AEGIS exposes a control plane for evaluating, testing, observing, securing, and verifying AI systems. The API is the machine interface to that control plane:

- **REST, JSON over HTTPS.** The API follows resource-oriented REST conventions. Requests and responses are JSON unless a content type is explicitly negotiated. All traffic is HTTPS.
- **Implemented with FastAPI.** The API server is FastAPI, described in `README.md` and `docs/architecture/high-level-architecture.md`. FastAPI generates the OpenAPI schema that forms the contract baseline.
- **Versioned.** The API is versioned in the URL path (`/v1/...`). Breaking changes require a new major version. See `versioning-policy.md`.
- **Synchronous for control-plane reads and creates.** Listing, reading, creating, updating, and deleting configuration resources (projects, targets, datasets, evaluators, policies) is synchronous: the client sends a request and receives a complete response.
- **Asynchronous for experiment execution.** Running an experiment is long-running and is executed asynchronously against a worker pool. The API returns a `202 Accepted` with a run and execution identity and status endpoint; the client polls or subscribes via webhook. See `async-execution-contract.md`.
- **Uniform error contract.** Every error is reported in the same envelope with a machine-readable code, a human-readable message, structured details, and a request ID. See `error-contract.md`.
- **Bearer token and scoped API key authentication.** Users authenticate with bearer tokens; service accounts for CI/CD and automated evaluation authenticate with scoped API keys. See `authentication-and-authorization.md`.

## Design Stance

The API is designed around the principle derived from grilling.md and the architecture documentation:

```text
Fail predictably under unpredictable conditions.
```

Concretely, this means:

- Every mutating call passes an explicit pipeline: Authentication, Authorization, Validation, Application Service, Transaction. See `write-architecture.md` and `api-design.md`.
- Authorization is enforced at the API layer and re-checked in the application service; transport-level checks are never trusted alone. See `security-architecture.md`.
- Error responses are uniform, never leak stack traces, and are classified as retryable or non-retryable. See `error-contract.md` and `failure-architecture.md`.
- Long-running work is idempotent and retried with bounded backoff; retries never duplicate side effects. See `async-execution-contract.md` and `failure-architecture.md`.
- Webhooks are the preferred delivery mechanism for completion events on long asynchronous flows, with polling as a fallback. See `webhooks.md`.

The REST contract is the source of truth for client compatibility. The API may not change in a breaking way without a contract review, per `versioning-policy.md`, the contract testing rules in `docs/testing/contract-testing.md`, and the CI/CD PR gates.

## Resource Model

The API exposes the following resource model. Every tenant-owned resource carries explicit `organization_id` and `project_id` ownership and is scope-bound at lookup time.

| Resource | Description |
|---|---|
| Organization | The top-level tenant. Owns projects, membership, billing, and tenancy. |
| Project | A team-scoped container within an organization. Owns targets, datasets, experiments, evaluators, policies, and reports. |
| Target | A registered AI system that AEGIS can invoke or observe (LLM app, RAG pipeline, agent, multi-agent system, classifier, extraction system, model API). |
| Target Version | An immutable, reproducible configuration snapshot of a Target at a point in time (model, provider, prompt, tools, retrieval configuration, memory policy, guardrails, runtime, code/build identity). |
| Dataset | A versioned collection of evaluation scenarios. |
| Test Case | A single executable and evaluable scenario within a Dataset Version. |
| Experiment | A reproducible evaluation configuration executed against a Target Version (target, dataset, evaluators, policies, environment, execution settings). |
| Run / Execution | An asynchronous execution of an Experiment against a Target Version with a Dataset Version. A Run is the user-facing unit; an Execution is the internal record of a specific invocation. |
| Metric Result | A scored outcome for an execution, linked to a Target Version, Dataset Version, Evaluator Version, Execution, and Evidence. |
| Report | An analysis artifact (regression, failure, comparison) generated from results. |
| Policy | A versioned, non-compensatory rule set governing gates and verdicts. |
| Gate verdict | The outcome of evaluating results against a Policy at a deployment or promotion gate. |
| Audit | The append-only record of every mutating operation, including identity, action, object, before/after state, and timestamp. |

Immutability is a core invariant. Target Versions, locked Dataset Versions, Experiment and evaluator snapshots, and historical Results are immutable; writes to them are rejected. See `write-architecture.md`.

## OpenAPI Specifications

The OpenAPI/Swagger specifications for each API major version live in the `openapi/` subdirectory of this folder. The specs are generated from code contracts and audited to enforce parity with the tests. See `openapi/README.md`.

## Document Index

The API documentation is organized as follows. Read them in the order listed.

1. **`README.md`** — this file: purpose, design stance, resource model, OpenAPI location, and document index.
2. **`api-design.md`** — general design rules: resource-oriented URLs, HTTP semantics, collection querying, the write pipeline, ID and timestamp conventions, a flow diagram for resource writes, and the primary API groups.
3. **`api-conventions.md`** — operation conventions: verb semantics, filtering, field selection, sorting, pagination, conditional requests, idempotency, request IDs, rate limiting, and error consistency.
4. **`authentication-and-authorization.md`** — bearer tokens, service accounts, scoped API keys, permissions and roles, tenant scoping, authorization enforcement across layers, and the request authorization path.
5. **`async-execution-contract.md`** — the contract for asynchronous experiment execution, run resource representation, idempotency, and terminal state semantics.
6. **`error-contract.md`** — the uniform error envelope, standard error codes, retryability classification, and error-to-HTTP mapping.
7. **`versioning-policy.md`** — URL path versioning, additive vs breaking changes, the deprecation lifecycle, and the distinction between API versions and internal resource versions.
8. **`webhooks.md`** — subscription resources, signature verification, bounded retry, ordering, idempotent delivery, and the relationship to polling.
9. **`openapi/README.md`** — what lives in the OpenAPI folder, spec governance, and file naming conventions.
