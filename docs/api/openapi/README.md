# OpenAPI Specifications

This directory holds the OpenAPI/Swagger specifications for the AEGIS API. The specs are the machine-readable representation of the API contract described throughout `docs/api/`, and they are the baseline that contract tests enforce.

## What Lives Here

This folder contains:

- **One OpenAPI specification per API major version**, named per the convention below. The current major version is the source of truth for clients; older major versions remain available for reference during their deprecation window (see `versioning-policy.md`).
- **Generated schemas** produced from the code contracts. Because AEGIS is implemented with FastAPI, the OpenAPI schema is generated from the code and validated against the documented contract.
- **Reference artifacts** used by contract tests and tooling, where applicable.

The folder does not contain the runtime-validated contract tests themselves; those live under `docs/testing/contract-testing.md` and the test suites referenced there. This folder is the contract baseline the tests verify against.

## Source of Truth: Code Contracts or Spec-First

AEGIS is implemented with FastAPI, and the OpenAPI schema is generated from the code. The working decision is:

- **The implementation (FastAPI) is the primary source of the wire contract.** The OpenAPI spec is generated from the code via the FastAPI framework.
- **The generated spec is validated for parity against the documented contract** and the contract tests. The documented contract in `docs/api/` and the enforced behaviors in the tests are authoritative for intent; a generated spec that contradicts the documentation or an enforced behavior is a defect, not a new truth.

This is the code-first stance. If a future capability changes this decision to spec-first (people authoring the spec first and generating code from it), this document and `versioning-policy.md` must be updated to reflect the change; until then, code-first governs.

### Keeping the Spec in Sync with Code

The spec stays in sync with the code through the CI/CD pipeline:

- Generating the OpenAPI schema is part of the build for each supported API major version.
- **Contract tests enforce parity**: the contract tests (see `docs/testing/contract-testing.md`) assert that the generated spec matches the committed spec in this folder and that documented behaviors hold. Any code change that alters the generated spec without a corresponding, reviewed contract change fails CI.
- Contract reviews are a PR gate, per `versioning-policy.md`. Additive changes and breaking changes both pass through this gate, but breaking changes require a new major version.

The parity guarantee is what makes this folder trustworthy: the spec here matches the code that is actually deployed for each supported major version.

## How to Read the Catalog

Each major-version spec is a complete OpenAPI document describing the endpoints, request/response schemas, error codes, and security schemes for that version:

- **`/v1/...`** — the current supported major version. Clients integrate against this.
- **Older versions** — retained during their deprecation window for migration; see their `Deprecation`/`Sunset` headers and `versioning-policy.md`.

Within a spec:

- **Errors** follow the uniform envelope and codes from `error-contract.md`.
- **Security** follows `authentication-and-authorization.md` (bearer tokens and scoped API keys).
- **Async operations** follow `async-execution-contract.md` (202 + status endpoint).
- **Webhooks** follow `webhooks.md` (subscription endpoints and event schemas).

## Naming Convention

Specification files are named by API major version:

```text
openapi-v1.json
openapi-v1.yaml
openapi-v2.json
...
```

- The current major version file is always present and always matches the currently deployed code.
- A new major version adds a new file (for example, `openapi-v2.json`) while the prior major version file remains during its deprecation window.
- The format (JSON or YAML) is consistent within the release; the schema references the same contract and passes the same parity tests.
- Optional auxiliary files (for example, event schemas for webhooks) are named descriptively and referenced from the major-version spec.

Each major-version file corresponds to exactly one contract-test suite, per `versioning-policy.md`.

## References

- `docs/api/README.md` — overview and document index.
- `docs/api/versioning-policy.md` — how API versions map to specs and contract tests.
- `docs/testing/contract-testing.md` — parity enforcement and PR gates.
- The architecture documents in `docs/architecture/` (FastAPI, modular monolith).
