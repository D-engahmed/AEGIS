# API Change Protocol

## Purpose and Authority

This document is the required process for changing the AEGIS API. It is governed by `docs/api/versioning-policy.md` and enforced by the contract-testing gates (`docs/testing/contract-testing.md`, `docs/ci-cd/pull-request-gates.md`). Every endpoint is a promise to its consumers — the worker, the SDK, the dashboard, and webhook subscribers. A change to the wire contract that breaks a consumer is an incident that only happens after the fact if the protocol was skipped.

The operating rule from the product facts:

```text
A change to a contract is a breaking API change.
Fail predictably under unpredictable conditions.
```

## The Protocol Steps for Any API Change

### Step 1: Check Contract Tests

Before designing anything, inspect the existing contract tests for the affected surface (`docs/testing/contract-testing.md`). The contract tests assert parity between the OpenAPI spec and the implemented code, and enforce documented behaviors. They are the current statement of the promise your change is about to modify. If no contract test exists for the surface you are changing, that is itself a defect to fix before proceeding.

### Step 2: Classify Additive vs Breaking

Classify every change against `docs/api/versioning-policy.md`:

```text
Additive  New endpoint; new OPTIONAL request/response field; new response field
          leaving existing fields unchanged; new error code that does not change
          the meaning of an existing code for the same condition.

Breaking  Removing or renaming a field; changing a field's type, format, or
          semantics; removing or renaming an endpoint; changing request/response
          in a way that breaks existing clients; changing the meaning of an
          existing error code for the same condition.
```

If any part of the change is breaking, the whole change is treated as breaking for gating purposes. You do not ship "mostly additive plus one small rename."

### Step 3: Breaking Requires a New Major Version and Contract Review

A breaking change requires:

1. A new major path version (`/v2/...`) introduced alongside the current version during a transition period.
2. An explicit **contract review** — the change is reviewed for consumer impact and approved before it can merge.
3. Release notes and changelog entries describing the breaking change and the migration path.

Additive changes remain under the current major version but still pass contract tests and CI gates. The contract is the source of truth for client compatibility; changing it in a breaking way is a deliberate, reviewed decision, never an incidental side effect.

### Step 4: Update the OpenAPI Spec

Update the OpenAPI specification for the affected major version before implementing the handler. The spec is the contract the tests enforce: one major API version corresponds to one OpenAPI spec and one contract-test suite that must stay in parity (see `docs/api/openapi/README.md`). The spec change is part of the change, not documentation trailing the code.

### Step 5: Update API Documentation

Update the affected API documentation: `docs/api/api-design.md` for endpoint semantics, `docs/api/error-contract.md` if error behavior changed, `docs/api/async-execution-contract.md` if execution semantics changed, `docs/api/authentication-and-authorization.md` if scopes or auth changed. If the versioning policy or conventions themselves must change, that is a change to `docs/api/versioning-policy.md` / `docs/api/api-conventions.md`, handled as an architecture-level change with review, not a side effect.

### Step 6: Update Contract Tests FIRST (Consumer-Driven), Then Implement

The contract tests are updated **before** the implementation:

1. Update the consumer side of the contract first: declare the subset of the contract the consuming code relies on, in consumer-driven form.
2. Update the producer-side expectations (OpenAPI parity, schema snapshots, error contract) to match.
3. Watch the updated tests fail against the current implementation — that failure is the definition of the change.
4. Implement the handler until the updated contract tests pass.

Contract-first ordering proves the change is real: if you can make the updated contract pass, the change is complete; if not, the change is not done no matter how well the code runs. Every boundary the change crosses — API to client, worker to queue, worker to target adapter, adapter to evaluator, webhooks — is contract-tested the same way (`docs/testing/contract-testing.md`).

### Step 7: Keep Response Shape Stable During Transitions

During any compatibility transition:

```text
No silent renames. No silent type changes. No silent removal.
Existing fields keep their names, types, and semantics until the
consumer has migrated and the old version is sunset.
```

Apply the same discipline the data layer uses: expand before contract. Add the new field or endpoint alongside the old, keep both working, and only remove the old representation after every consumer has migrated and the deprecation lifecycle has run (`docs/api/versioning-policy.md` deprecation lifecycle). A renaming that "looks the same" to a human is a break to a machine.

### Step 8: Deprecation Announcements

Deprecated endpoints follow the documented lifecycle:

1. **Announce** — release notes, changelog, and updated OpenAPI specs state the intended replacement and the target sunset date.
2. **Deprecation header** — the endpoint begins returning `Deprecation` and/or `Sunset` headers.
3. **Grace period** — old and new coexist so clients can migrate.
4. **Sunset** — after the announced date, removal is itself a breaking change with the same contract review.

SDKs and tooling surface deprecation warnings so consumers learn of the change at dev time, not at runtime.

### Step 9: Update the API README Index

If the change adds a new collection, action, or resource, update `docs/api/README.md` so the index reflects the current surface. A documented index that omits a live endpoint is a documentation defect; a listed endpoint with no implementation or contract test is a different defect — both are blockable at review.

### Step 10: Trace the Consumer Impact List

Every response change affects consumers. The response change is not done until the impact is traced:

```text
Consumers of any response:
├── Worker(s)           — parses execution and evaluation payloads
├── SDK                 — serializes/deserializes client payloads
├── Dashboard           — renders results and verdicts
└── Webhook subscribers — receive event payloads
```

For each consumer, determine in the impact trace what it reads from the response and whether the change is additive (still compatible), breaking (requires coordination and a new major version landing together), or requires a worker/SDK version change to be deployed in the same window. Additive changes are compatible by definition once you have verified each consumer. Breaking changes are landed producer-and-consumer together so no version of the system is left in a broken state (`docs/testing/contract-testing.md`).

## Enforcement Summary

| Change class | New major version | Contract review | Contract tests first | Consumer impact traced |
|---|---|---|---|---|
| Additive | No | No | Yes | Yes (verify compatibility) |
| Breaking | Yes | Yes | Yes | Yes (coordinate together) |
| Deprecation/Sunset | At sunset | Yes | Yes | Yes |

## Related Documentation

- `docs/api/versioning-policy.md` — the versioning rules this protocol operationalizes.
- `docs/testing/contract-testing.md` — contract disciplines and parity enforcement.
- `docs/api/error-contract.md` — the uniform error contract that any response change must preserve.
- `docs/api/async-execution-contract.md` — execution-async payload semantics.
- `docs/api/webhooks.md` — the webhook event payload contract.
- `docs/api/README.md` — the API index updated when collections change.
- `docs/ci-cd/pull-request-gates.md` — the PR gates that enforce contract review.