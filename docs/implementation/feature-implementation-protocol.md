# Feature Implementation Protocol

## Purpose

This is the exact protocol for implementing a feature in AEGIS. It is the operating detail behind the workflow in `docs/implementation/agent-implementation-guide.md`: the workflow says what to do in what order; this protocol fixes the sequence of steps and, for each step, what "doing the step" looks like and what condition proves the step is complete.

The 14 steps below are normative. Do not reorder them, do not skip them, and do not merge two steps into one to "move faster." Each step has an exit condition, and a step is not passed until its exit condition is satisfied.

## The Protocol

```text
Step 1:
Read Requirements.

Step 2:
Identify impacted architecture layer.

Step 3:
Check ADRs.

Step 4:
Check database impact.

Step 5:
Check API impact.

Step 6:
Define failure cases before implementation.

Step 7:
Write/Update tests.

Step 8:
Implement smallest correct change.

Step 9:
Run local validation.

Step 10:
Run integration tests.

Step 11:
Update documentation.

Step 12:
Run CI.

Step 13:
Review architecture boundary violations.

Step 14:
Mark complete only if acceptance criteria pass.
```

## Step Detail

### Step 1: Read Requirements

**How.** Read the functional and non-functional requirements (and `grilling.md` for the governing product facts). Identify what the feature must do, what constraints apply, and what is out of scope. If the task is a bug report or a one-line request, convert it into the acceptance-criteria form of `docs/requirements/acceptance-criteria.md` before proceeding. Every acceptance criterion must be objectively verifiable.

**Exit condition.** You can state, in one paragraph: the requirement(s) served, the acceptance criteria that prove completion, and the explicit out-of-scope list. If any of the three is unknown, the step is not passed.

### Step 2: Identify impacted architecture layer

**How.** Determine the primary layer (00-11) using the layer table in `docs/development/README.md` and the rules in the respective layer files. If the feature spans layers, list the primary layer and the interaction points, and confirm each boundary crossing is legal per `docs/development/dependency-rules.md`. Read the layer file for the primary layer before designing.

**Exit condition.** You can name the primary layer, the interaction points, and cite the layer rule that authorizes each crossing. A feature assigned to no layer, or to a layer by guesswork, does not pass.

### Step 3: Check ADRs

**How.** Read the accepted ADRs in `docs/architecture/architecture-decision-records/`. Confirm the feature extends the system the way the ADRs intended. If the feature contradicts an ADR, or requires a new architecture decision, mark it as an architecture-violation blocker now and follow the ADR proposal path in `docs/implementation/agent-implementation-guide.md` — implementation does not start while blocked.

**Exit condition.** Either (a) the feature is consistent with all relevant ADRs, or (b) the conflict is documented and an ADR proposal is open. Proceeding to implementation with an unresolved ADP is not allowed.

### Step 4: Check database impact

**How.** Determine whether the feature needs a new table, column, constraint, index, type change, or backfill. If yes, design the change as a migration per `docs/implementation/database-change-protocol.md` and `docs/data/schema-evolution.md`. Classify the migration as additive or destructive. Confirm it never touches immutable rows: write-once results, locked dataset versions, published target/evaluator versions, executed experiment snapshots. If the design would ever rewrite an immutable row, the correct answer is a new version entity, not a schema mutation.

**Exit condition.** A yes/no database-impact statement with the migration files designed, its additive/destructive classification recorded, and an immutability check covering every table the migration touches.

### Step 5: Check API impact

**How.** Determine whether the feature adds, removes, renames, or changes the semantics of any request, response, field, error code, or endpoint. If yes, classify as additive or breaking per `docs/api/versioning-policy.md` and follow `docs/implementation/api-change-protocol.md`. Arrange the contract tests first, update the OpenAPI spec, and trace every consumer of the changed surface (worker, SDK, dashboard, webhook subscribers).

**Exit condition.** An API-impact statement covering every endpoint and field touched, an additive/breaking classification, and (for breaking changes) an approved contract review with a new major version path. Silent or unreviewed response changes do not pass.

### Step 6: Define failure cases before implementation

**How.** Enumerate what can go wrong before writing the feature code: no evidence produced, timeout, retry exhaustion, cancellation, a locked-version edit attempt, malformed input, provider failure, cross-tenant access, evaluator plugin crash. For each, specify the expected failure behavior under `docs/development/error-handling.md` (typed errors, retryability classification) and the failure-mode test that will prove it. AEGIS behavior is only correct when it fails predictably.

**Exit condition.** A written list of failure cases, each with an expected behavior and a named test that will exercise it. No failure case that is part of the feature's contract may go untested.

### Step 7: Write/Update tests

**How.** Write the tests that define the feature before (or with) the implementation: unit tests for behavior, failure-mode tests from Step 6, contract tests for any crossed boundary, and integration tests where the feature involves storage, queueing, or target invocation. Follow the test conventions in `docs/testing/testing-strategy.md`, `docs/testing/unit-testing.md`, and `docs/testing/contract-testing.md`. Per `docs/testing/test-environments.md`, unit and fast integration run locally; `expensive` suites are tagged, never implicit.

**Exit condition.** The test suite for the feature exists and fails or is red until the feature is implemented. Tests written after the fact to certify finished code are not the point of this step; the tests define the contract the code must satisfy.

### Step 8: Implement smallest correct change

**How.** Implement the minimal change that satisfies the acceptance criteria and the tests, following `docs/development/coding-standards.md` and `docs/development/error-handling.md`. Respect the smallest-correct-change rule: no unrelated fixes, no speculative generality, no feature claims that were not requested. Do not work around an architecture violation — surface it.

**Exit condition.** The feature's tests pass, the change is scoped to the feature, and a diff review finds nothing the task did not ask for.

### Step 9: Run local validation

**How.** Run the local validation commands defined in `docs/development/coding-standards.md` and the gate set in `docs/ci-cd/pull-request-gates.md`: lint, typecheck, unit tests, contract tests, migration tests if a schema change exists. The local tier uses contained PostgreSQL and Redis with recorded fixtures and fake providers; it never points at shared, staging, or production infrastructure (`docs/testing/test-environments.md`).

**Exit condition.** All local validation commands pass with no errors. A skipped test or a locally disabled check does not count as passing.

### Step 10: Run integration tests

**How.** Run the integration tests that exercise the feature across components: application plus schema plus queue where involved, contract suites at each crossed boundary, and end-to-end checks at the feature's level of integration (`docs/testing/integration-testing.md`, `docs/testing/end-to-end-testing.md`). These run in CI with real contained PostgreSQL and Redis; staging-level suites run against production-shaped staging per `docs/testing/test-environments.md`.

**Exit condition.** The integration surface of the feature passes: multi-component behavior, evidence linkage, tenant isolation, and immutability invariants verified by tests, not by inspection.

### Step 11: Update documentation

**How.** Update every affected document and only those: requirements if acceptance criteria changed, API specs and `docs/api` READMEs for interface changes, `docs/data` docs for schema changes, layer files for new patterns, and this implementation folder if the change alters how work is done. Documentation that contradicts the delivered code is a defect (see `docs/implementation/agent-implementation-guide.md` Step 13).

**Exit condition.** A review of the diff shows no document that contradicts the code, and all documentation touched by the feature is consistent with the requirements, the API, and the schema.

### Step 12: Run CI

**How.** Open the change against the CI gates and let the full per-PR gate set run: static analysis, unit, contract, security scans, schema-drift and migration gates, and the selective integration set defined in `docs/ci-cd/pull-request-gates.md`. Local results are a preview; CI is the signal for the shared repository.

**Exit condition.** CI passes with no unexplained or waived failures. Any gate that the change cannot pass is a problem to fix in the change, not a reason to weaken the gate.

### Step 13: Review architecture boundary violations

**How.** Perform the final architecture review: layer placement correct, dependency direction legal, no forbidden imports in domain code, no direct infrastructure access from layer 01, no silent contract changes, immutability and evidence rules intact. Check the change did not widen scope to reach around a boundary it should not cross.

**Exit condition.** The change passes the architecture review with no violations, or the review produced a documented, accepted ADR and the change implements it. An unreviewed boundary crossing is a rejected change.

### Step 14: Mark complete only if acceptance criteria pass

**How.** Verify every acceptance criterion from Step 1 is objectively true, the Definition of Done checklist (`docs/implementation/definition-of-done.md`) is satisfied with proof, and the requirements traceability is recorded (`docs/requirements/traceability-matrix.md`). Then mark the feature complete.

**Exit condition.** All acceptance criteria pass and every Definition of Done item has proof. There is no completion without this step.

## Related Documentation

- `docs/implementation/agent-implementation-guide.md` — the workflow this protocol operationalizes.
- `docs/implementation/definition-of-done.md` — the completion gate referenced by Step 14.
- `docs/implementation/database-change-protocol.md` — required when Step 4 is "yes".
- `docs/implementation/api-change-protocol.md` — required when Step 5 is "yes".
- `docs/requirements/acceptance-criteria.md` — the acceptance-criteria template used in Step 1 and Step 14.
- `docs/testing/` — the test strategy, environments, and specific test disciplines for Steps 6-10.
- `docs/ci-cd/pull-request-gates.md` — the CI gate set for Steps 9 and 12.