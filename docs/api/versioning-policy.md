# Versioning Policy

This document defines how the AEGIS API versioned and how it evolves without breaking its consumers. It distinguishes API versioning (the public contract) from internal resource versioning (Target Versions, Dataset Versions, Evaluator Versions), which are two different mechanisms that serve different purposes.

## URL Path Versioning

The API is versioned in the URL path:

```text
/v1/organizations/{organization_id}/projects/{project_id}/...
```

- The major version is a required prefix on every endpoint.
- A breaking change requires a new major path version (`/v2/...`), which is introduced alongside the current version during a transition period.
- The current major version is the only one guaranteed to be stable. Older major versions are retired according to the deprecation lifecycle below.

## Additive vs Breaking Changes

### Additive Changes (Minor / Compatible)

Additive changes may be released under the current major version:

- New **optional** request or response fields (client and server remain compatible with existing payloads).
- New endpoints (adding a collection or action does not break existing clients).
- New response fields (so long as existing fields are unchanged).
- New error codes that do not change the meaning of existing codes for the same condition.

Additive changes must still pass contract tests and CI gates, but they do not require a new major version.

### Breaking Changes (Require a New Major Version)

The following require a new major version:

- Removing or renaming a field.
- Changing a field's type, format, or semantics.
- Removing or renaming an endpoint.
- Changing a request or response in a way that breaks existing clients.
- Changing the meaning of an existing error code for the same condition.

Breaking changes are agreed and announced, and the old major version is kept available until its sunset date.

## The Deprecation Lifecycle

Deprecated endpoints follow a documented lifecycle:

1. **Announce** — The deprecation is announced (release notes, changelog, and updated OpenAPI specs) with an intended replacement and a target sunset date.
2. **Deprecation header** — The deprecated endpoint begins returning a `Deprecation` response header and/or a `Sunset` header, signaling to clients that the endpoint will be removed.
3. **Grace period** — The current and deprecated versions coexist. Deprecated functionality continues to work so clients can migrate.
4. **Sunset** — After the announced date, the deprecated functionality is removed. It follows the same contract-change review as any breaking change.

Clients should monitor `Deprecation`/`Sunset` headers and migrate before the sunset date. SDKs and tooling SHOULD surface deprecation warnings to developers.

## Contract-Review Gate

The API may not break its contract without a contract review. This is enforced by the CI/CD PR gates and the contract testing rules in `docs/testing/contract-testing.md`:

- Contract tests assert parity between the OpenAPI spec and the implemented code and enforce that documented behaviors hold.
- A change that removes, renames, or changes the semantics of a field, endpoint, or error code is flagged and cannot merge without an explicit contract-review approval and a new major version.
- Additive changes are validated against the existing contract so they cannot inadvertently break a consumer.

The contract is the source of truth for client compatibility; changing it in a breaking way is a deliberate, reviewed decision, not an incidental side effect.

## Internal Resource Versions vs API Versions

Internal resource versions are a different mechanism from API versions and must not be confused:

- **API version** (`/v1/...`): the version of the public interface contract. It changes only when the public contract changes (breaking changes).
- **Internal resource versions** (Target Version, Dataset Version, Evaluator Version): immutable configuration snapshots of domain entities. They capture the exact state of an AI system, evaluation dataset, or evaluator at a point in time to guarantee reproducibility and provenance (`write-architecture.md`, `README.md`).

Key distinctions:

| Concern | API version | Internal resource version |
|---|---|---|
| What is versioned | The public wire contract | Domain entity configuration snapshots |
| Changes when | Public contract breaks | Configuration/model/prompt/evaluator changes |
| Immutability | Version coexists during transition | Versions are immutable once created/locked |
| Purpose | Client compatibility | Reproducibility and provenance ("no score without evidence") |
| Examples | `/v1`, `/v2` | `target_version_id`, `dataset_version_id`, `evaluator_version_id` |

An experiment pins its configuration by referencing internal resource versions (`target_version_id`, `dataset_version_id`, `evaluator_version_ids`, `policy_version_id`). Changing an internal resource version does not change the API version; the two evolve independently. Creating a new internal resource version has no effect on the API path version.

Internal resource immutability is tightly coupled to internal versioning:

- A Target Version is immutable once referenced by an experiment.
- A Dataset Version is immutable once locked.
- An Evaluator Version is immutable once versioned.

These guarantees are enforced in the application service (`write-architecture.md`). Internal version changes that would alter the meaning of historical records are prevented by that immutability, regardless of API versioning.

## How the API Version Maps to Contract Tests

- Each API major version has a corresponding contract test suite and OpenAPI spec (see `openapi/README.md`).
- The test suite for a major version asserts that the deployed endpoints match the spec of that major version and that documented behaviors hold.
- CI enforces that no change to the code breaks a currently supported major version's contract without going through the deprecation and major-version process.
- The mapping is: one major API version → one OpenAPI spec → one contract-test suite that must stay in parity.

## References

- `docs/testing/contract-testing.md` — parity enforcement and PR gates.
- `openapi/README.md` — spec storage and naming.
- `docs/architecture/write-architecture.md` — internal resource immutability.
- `docs/architecture/component-architecture.md` — service boundaries.
