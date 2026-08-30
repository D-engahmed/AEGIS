# Acceptance Criteria

## Purpose

Acceptance criteria tell an agent when a feature is complete. The agent does not only know the Requirement; it must know when the Feature is accepted. Acceptance criteria are derived from functional requirements and must be objectively verifiable. Every criterion must be either true or false; no criterion may be ambiguous or subjective.

## Worked Example

```text
Feature:
Experiment Execution

Accepted only when:

- Experiment is immutable after execution begins.
- Every execution has a unique ID.
- Retry is bounded.
- Retry cannot duplicate side effects.
- Cancellation works.
- Partial evidence is preserved.
- Failed execution is distinguishable from cancelled execution.
- All tests pass.
- API contract is updated.
- Documentation is updated.
```

## Template for New Acceptance Criteria

When authoring acceptance criteria for a new feature, use the following template:

```text
Feature:
<Feature Name>

Accepted only when:

- <Criterion 1 — must be objectively verifiable>
- <Criterion 2 — must be objectively verifiable>
- <Criterion 3 — must be objectively verifiable>
- <Criterion N — must be objectively verifiable>
- All tests pass.
- API contract is updated.
- Documentation is updated.
```

## Rules

1. Every acceptance criterion must be derived from a functional requirement.
2. Every criterion must be objectively verifiable (true or false).
3. No criterion may be vague, aspirational, or subjectively judged.
4. The final three criteria (all tests pass, API contract updated, documentation updated) are mandatory for every feature.
5. Acceptance criteria are a gate: a feature is not done until every criterion is satisfied.
