# Contract Testing

## Why Contracts Matter

AEGIS is a chain of independently developed components. From the user's perspective there is one system, but in reality a request flows across several ownership and transport boundaries:

```text
Control Plane
↓
Worker
↓
Target Adapter
↓
Evaluator Plugin
```

Each arrow is a contract. A contract is a promise about the shape and meaning of data that crosses a boundary: field names, types, requiredness, semantics, error behavior, and versioning rules. If any contract changes silently, the downstream consumer breaks in production, not in development. The purpose of contract testing is to discover contract drift before production.

The rule from `grilling.md` and the API documentation applies to every boundary in the chain:

```text
Fail predictably under unpredictable conditions.
A change to a contract is a breaking API change.
```

## What Is Contract Tested

### API to Client

- **OpenAPI schema parity**: the generated OpenAPI specification must be byte-for-byte consistent with the contract declared in tests. A code change that alters the schema without a deliberate contract change fails.
- **Request and response compatibility**: every documented endpoint is exercised against the schema — required fields, optional fields, constraints, and examples must match the schema.
- **Error contract**: responses follow the uniform error envelope (machine-readable code, human message, structured details, request ID) and retryability classification from `docs/api/error-contract.md`.
- **Versioning policy**: endpoints are versioned in the URL path; only additive changes are allowed within a major version. See `docs/api/versioning-policy.md`.

### Worker to Queue

- **Job payload contract**: the shape of a job published to the queue — execution ID, idempotency key, target version reference, dataset version reference, experiment configuration — is pinned. A producer and a consumer that disagree on the payload fail the contract.
- **Redelivery semantics**: payloads must carry what a worker needs to reconstruct work after redelivery without duplicating side effects.

### Worker to Target Adapter

- **Target invocation contract**: how the worker invokes a target — request envelope, headers or equivalent metadata, timeout and cancellation semantics, and how responses are returned.
- **Adapter request and response**: the contract between the worker and the target adapter for black-box HTTP targets, SDK targets, and observed targets. Each adapter must honor the invocation contract for both success and failure paths.
- **Failure mapping**: adapter errors map to the failure taxonomy (timeout, provider rate limit, malformed response, non-retryable, deterministic) in a contractually fixed way.

### Adapter to Evaluator

- **Evaluator plugin interface per ADR-004**: every evaluator plugin implements `evaluate()`, `validate()`, and `metadata()`. Contract tests pin the interface signature, the serialization format across the RPC boundary, and the payload envelope for `MetricResult`, including score, reason, confidence, evaluator identity and version, and judge prompt version where applicable.
- **Addressing practice**: contract tests run against the plugin boundary itself, so a change to the evaluator SDK or to a plugin implementation is caught on both sides of the boundary.

### Webhooks

- **Event payload**: webhook delivery events (run completed, failed, cancelled, verdict produced) have a pinned payload contract including event type, IDs, timestamp, and signature-relevant fields.
- **Delivery contract**: bounded retry, ordering, and idempotent delivery per `docs/api/webhooks.md` are verified, so a subscriber implements against the documented contract and is not surprised.

## Techniques

Two complementary techniques are used:

- **Consumer-driven contracts**: the consumer declares the subset of the contract it relies on; the producer's tests must satisfy the consumer's expectations. This catches a producer change that breaks a real consumer without having to run the full system.
- **Schema-snapshot testing**: serialized schemas and representative payloads are stored as reviewed snapshots. Any drift in the generated OpenAPI schema, job payload, adapter envelope, or event payload fails the test. Unlike prompt snapshots, these snapshots are structural and their purpose is stability, not behavior approximation.

## Enforcement

A breaking change to any contract fails the PR gate. The gate is defined in `docs/ci-cd/pull-request-gates.md`, and contract suites run on every change that touches a boundary. Because a contract change is a breaking API change, it must follow `docs/api/versioning-policy.md`: negotiate the change with consumers, additively where possible, and land the consumer change and the producer change together so no version of the system is left in a broken state.