# Testing Strategy

## Purpose

The testing strategy defines what AEGIS tests at each level, how it tests AI systems (which differ from deterministic software), and how it proves the evaluation machinery itself is trustworthy. The strategy derives from `grilling.md`: AEGIS must apply software-engineering-grade testing and reliability discipline to probabilistic AI, and must test the system that tests the AI.

## What to Test at Each Level

### Unit

Unit tests cover the pure reasoning of the control plane: domain rules, policies, gate logic, retry classification, validation, evaluator logic, and statistics. They run with no real database, Redis, LLM, or provider, using pure functions, dependency injection, and fakes for ports. See `docs/testing/unit-testing.md`.

Units that must be unit tested:

- Domain rules: project, target, dataset, and experiment invariants.
- Policies: permission composition, policy versioning, non-compensatory rule evaluation.
- Gate logic: how verdicts (pass, warn, block, human override) are computed from results and thresholds.
- Retry classification: rolling failures into retryable, non-retryable, and deterministic classes.
- Validation: schema validation, identifier rules, input robustness classification.
- Evaluator logic: deterministic metric computation and evaluator adapter behavior.
- Statistics: aggregation, slicing, percentiles, confidence intervals, and regression math.

### Integration

Integration tests combine the application with real contained infrastructure: the application against PostgreSQL, the worker against the real Redis-backed queue, the API against the database, and the plugin boundary against the evaluator RPC. Migrations are exercised, and idempotency and retry behavior are proven against the real queue. No real LLM or provider is used — recorded fixtures or fake providers stand in. See `docs/testing/integration-testing.md`.

Integration targets:

- Application plus PostgreSQL: persistence, transactions, and tenant scoping across the schema.
- Worker plus queue: claiming, retrying, canceling, and redelivery semantics with the real queue.
- API plus database: request-to-persistence behavior, including the write pipeline from `docs/architecture/write-architecture.md`.
- Plugin plus evaluator RPC: the isolation boundary from ADR-004 under realistic transport conditions.

### Contract

Contract tests pin the interfaces between components so that any contract change is discovered before production:

```text
Control Plane
↓
Worker
↓
Target Adapter
↓
Evaluator Plugin
```

Contract scope: API to client, worker to queue, worker to target adapter, adapter to evaluator, and webhook payloads. A breaking change to a contract fails the PR gate and requires the API versioning policy. See `docs/testing/contract-testing.md`.

### End-to-End

End-to-end tests execute full scenarios through every plane: create project, target, version, dataset, test cases, lock, evaluator, experiment, run, completion, failure inspection, baseline comparison, gate, and authorized override. E2E runs in staging with a clean seeded dataset and recorded provider responses. See `docs/testing/end-to-end-testing.md`.

## Testing AI Systems

LLM testing is not equivalent to normal unit testing. LLM outputs are often nondeterministic and semantically variable, so AEGIS separates what can be tested exactly from what must be tested behaviorally.

### Contract-Style Deterministic Tests Around the Model

The following are deterministic and are tested exactly:

- JSON schema validity of structured output.
- Tool invocation schema: tool names, required and allowed arguments.
- Authorization policy: what the model or agent is permitted to invoke.
- Required fields, maximum output length, and enum constraints.
- Policy violations that are mechanically detectable.
- Latency, token counts, cost, tool call accuracy, and error rates.

These run as ordinary deterministic assertions on the model contract; the model's answer is not involved.

### Behavioral Tests for Prompts

Prompts are tested through behavioral tests, not exact-snapshot overfitting. Snapshot tests overfit exact wording and fail when a model rephrases a correct answer. Behavioral and structural assertions test what matters:

- Semantic equivalence where exact text is not required.
- Structural properties: schema, required fields, tool usage, refusal behavior.
- Classifications: whether output is a refusal, a clarification request, a tool call, or a final answer.
- Input robustness: normal, ambiguous, incomplete, malformed, adversarial, abusive, nonsensical, contradictory, high-risk, and out-of-domain inputs.

### LLM Judges, Used Selectively and Calibrated

LLM-as-judge is useful but is never ground truth. AEGIS:

- Uses judges selectively, for semantics that resistance deterministic measurement (subjective quality, open-ended correctness, some safety judgments), not for what can be computed exactly.
- Treats each judge as a versioned AI dependency. Judges are identified and versioned; judge prompts are versioned; judge model changes create a new evaluator version.
- Prefers deterministic or low-variance judge settings where the provider supports them.
- Measures judge disagreement when multiple judges are used, and surfaces uncertainty with every score.
- Preserves confidence, evaluator identity, evaluator version, and judge prompt version on every judge-produced result.

Flaky metrics must not block by default. A score that wobbles under repeated evaluation is a candidate for flakiness analysis, not an automatic gate. Blocking is reserved for metrics that are stable and whose failure meaningfully prevents deployment.

## Evaluation Self-Testing

AEGIS tests the system that tests the AI. The evaluation itself is validated with calibration suites in which the evaluator is run against labeled examples and judged on its own accuracy.

- **Known-good calibration examples**: inputs labeled with the correct expected verdict, used to prove the evaluator does not false-negative.
- **Known-bad calibration examples**: inputs labeled with the expected failure, used to prove the evaluator does not false-positive.
- The evaluator's accuracy, precision, recall, and agreement with human labeling are measured on these labeled examples, and a judge that drifts from its calibrated accuracy is flagged.
- Human sampling feeds agreement analysis, which feeds metric calibration: automated evaluation is not trusted on its own claim.

An evaluator that cannot pass its own calibration suite is not deployable as a gate.

## Test Data

Test data strategy is covered in `docs/testing/test-data-strategy.md`. In short: test data must be realistic, adversarial, and include edge and invalid inputs; golden datasets calibrate evaluators; datasets are quality-checked for duplicates, near-duplicates, leakage, class imbalance, and coverage; public and private dataset splits prevent overfitting; synthetic data provides coverage but never replaces realism; recorded provider responses are fixtures for integration tests so no real LLM is used unless explicitly tagged; test data never contains real secrets or PII; and seeded deterministic data guarantees repeatability.

## Test Environments

Test environments are covered in `docs/testing/test-environments.md`. Each test class runs in the tier where it is safe and representative: local, CI sandbox, staging, or production. Parity rules require staging to model production topology and data volume; expensive or destructive suites (chaos, stress, red-team) are restricted to controlled environments.

## Relation to CI Gates

The CI/CD gates are defined in `docs/ci-cd/pull-request-gates.md`. The strategy and the gates are coupled:

- PR gates enforce static analysis, unit, contract, and security-scan suites on every change.
- Coverage policy prevents coverage from decreasing beyond the gate threshold.
- Breaking a contract fails the PR gate.
- Dependency-aware test selection decides which additional suites run based on the changed components.
- Expensive suites (stress, load, chaos, heavy evaluation) run on schedules, not per commit, and never gate a merge unless explicitly configured.
- Production deployment gates are configurable and non-compensatory: a critical safety failure blocks regardless of quality improvements.