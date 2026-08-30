# Definition of Done

## Rule

A Feature is not complete unless **ALL** of the following are satisfied:

```text
[ ] Requirement identified

[ ] Acceptance criteria defined

[ ] Correct layer selected

[ ] Architecture boundaries respected

[ ] Database migration created if required

[ ] API contract updated if required

[ ] Unit tests added

[ ] Integration tests added if required

[ ] Failure modes tested

[ ] Security implications reviewed

[ ] Observability added

[ ] Documentation updated

[ ] CI passes

[ ] Manual test path exists
```

## The Proof Rule

```text
An item without proof is not done.
```

Every checkbox is completed only when a **file, a test, a tool run, or a review record demonstrates it**. "I did this", "I believe this", and "I will do it later" are not proof. For each item below, the proof column names the artifact that must exist. If the artifact does not exist, the item is not done, and the feature is not done.

## Checklist Items and Their Proof

### 1. Requirement identified

**Proof.** The feature references at least one requirement in `docs/requirements/` (`functional-requirements.md` or `non-functional-requirements.md`), and the reference is recorded in `docs/requirements/traceability-matrix.md`. Features that exist to satisfy no requirement are rejected.

### 2. Acceptance criteria defined

**Proof.** Objectively verifiable acceptance criteria exist using the template in `docs/requirements/acceptance-criteria.md`, and every criterion is true/false verifiable. A feature whose acceptance criteria are vague, aspirational, or subjectively judged does not pass.

### 3. Correct layer selected

**Proof.** The primary layer (00-11) is identified in the implementation, consistent with `docs/development/README.md` and the layer file for that layer. The layer choice is visible in the code placement and confirmed in the change review.

### 4. Architecture boundaries respected

**Proof.** The change passes the architecture boundary review of `feature-implementation-protocol.md` Step 13: dependency direction is legal per `docs/development/dependency-rules.md`, no forbidden imports in domain code, no direct infrastructure access from layer 01, no unreviewed boundary crossing, and no contradiction of an accepted ADR. If the change required a new architecture decision, the ADR is accepted and referenced.

### 5. Database migration created if required

**Proof.** If the change touches the schema: a numbered migration exists per `docs/implementation/database-change-protocol.md`, classified additive/destructive, with `up`/`down`, an immutability check covering every touched table, and the CI migration gates passed. If the change has no schema impact, the review records "no schema impact" and that statement is the proof.

### 6. API contract updated if required

**Proof.** If the change touches the public surface: the OpenAPI spec and contract tests are updated first per `docs/implementation/api-change-protocol.md`, the additive/breaking classification is recorded, and the consumer impact list is traced. If the change has no API impact, the review records "no API impact."

### 7. Unit tests added

**Proof.** Unit tests for the changed behavior exist and pass in the local and CI tiers, per `docs/testing/unit-testing.md` and `docs/development/coding-standards.md`. Coverage of the changed code meets the project threshold enforced in CI.

### 8. Integration tests added if required

**Proof.** If the change crosses components (application + schema + queue + target + evaluator + evidence), integration tests exercise the full path and pass, per `docs/testing/integration-testing.md` and `docs/testing/test-environments.md`. Where a feature is integration-only by nature, the proof is the integration suite; a feature that needs integration coverage and lacks it fails this item.

### 9. Failure modes tested

**Proof.** The failure cases defined in `feature-implementation-protocol.md` Step 6 are each exercised by a test: timeout, retry exhaustion, cancellation, malformed input, locked-version edit attempt, cross-tenant access, provider failure, evaluator plugin crash. Expected failure behavior follows `docs/development/error-handling.md`. A feature with untested failure modes is not done.

### 10. Security implications reviewed

**Proof.** The change's security implications are reviewed against `docs/architecture/security-architecture.md` and `docs/development/layers/11-security-layer.md`: secrets handling, PII redaction, tenant isolation, authorization on every new/edited endpoint, and the security scan gate in `docs/ci-cd/pull-request-gates.md` passes. Security-sensitive findings are recorded and resolved; unresolved findings are blockers.

### 11. Observability added

**Proof.** The change emits the telemetry its behavior requires per `docs/development/layers/10-observability-layer.md`: relevant spans/traces for evaluation paths, structured logs, metrics, and alerting where the behavior is reliability-relevant. Absence of instrumentation where an operator would need it is a defect. Logs contain no secrets or PII; that is part of the proof.

### 12. Documentation updated

**Proof.** Every affected document is updated and consistent with the delivered code: requirements if acceptance criteria changed, API docs and OpenAPI for interface changes, `docs/data` for schema changes, layer files for new patterns, and the implementation folder if the change alters how work is done. The review verifies no document contradicts the code.

### 13. CI passes

**Proof.** The full per-PR gate set in `docs/ci-cd/pull-request-gates.md` passes: static analysis, unit, contract, security scans, schema-drift and migration gates, and the selective integration set. A waived or bypassed gate is not passing.

### 14. Manual test path exists

**Proof.** A documented manual test path exists and is reproducible for the feature — the steps an operator or QA person follows to see the feature behave in a running environment (`docs/testing/manual-user-testing.md`). For features covered entirely by automated smoke/end-to-end tests, the smoke path itself is the documented manual-verification analog. A feature that cannot be demonstrated by a documented path fails this item.

## Who Signs Off

Sign-off follows the change's scope and the role model in `docs/architecture/security-architecture.md`:

- **Author** completes every item and records proof.
- **Reviewer** verifies the proof exists and was not manufactured: the reviewer re-runs or re-inspects the evidence for items 1-14 where practical (diff review, CI status, test results, docs diff).
- **Owner/Admin** signs off on destructive migrations (danger review, `database-change-protocol.md` Rule 4), breaking API changes (contract review, `api-change-protocol.md`), and any security-sensitive or evidence-model change.
- **Data steward** participates when the change touches data meaning, classification, retention, or immutability boundaries.

For automated agents the author is the agent; the proof rule still applies. An agent does not "sign off" on its own unproven claims — the proof artifacts listed above are the sign-off, and a human reviewer verifies them before the change merges.

## Relationship to Acceptance Criteria

The acceptance criteria in `docs/requirements/acceptance-criteria.md` state what the feature must achieve to be accepted; this checklist states the engineering conditions that must hold for the feature to be complete. Both must pass. Acceptance criteria are false/true conditions on behavior; Definition of Done items are proof-bearing conditions on the engineering process. A feature that passes acceptance criteria informally ("it looked fine") still fails Definition of Done, and a feature whose checklist is ticked without passing acceptance criteria is not accepted. The mandatory closing criteria from the acceptance-criteria template — all tests pass, API contract updated, documentation updated — map directly to items 6, 7/13, and 12 of this checklist.

## Related Documentation

- `docs/requirements/acceptance-criteria.md` — the acceptance criteria template this checklist gates on.
- `docs/implementation/agent-implementation-guide.md` — the workflow whose final step is this checklist.
- `docs/implementation/feature-implementation-protocol.md` — the 14-step protocol whose Step 14 is this checklist.
- `docs/implementation/database-change-protocol.md` — proof for item 5.
- `docs/implementation/api-change-protocol.md` — proof for item 6.
- `docs/ci-cd/pull-request-gates.md` — proof for item 13.
- `docs/testing/` — proof for items 7, 8, 9, and 14.
- `docs/development/` — proof for items 3, 4, 10, and 11.