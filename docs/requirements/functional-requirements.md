# Functional Requirements

## How Requirements Are Authored

Functional requirements will evolve as AEGIS matures. Each requirement carries the following full attribute set. No attribute may be omitted. No extra attributes may be added beyond this template.

```text
Requirement ID
Name
Description
Priority
Actors
Preconditions
Input
Expected Behavior
Success Criteria
Failure Behavior
Security Impact
Data Impact
Dependencies
Related NFRs
Test Strategy
```

## Worked Example

```text
FR-EXE-01

Name:
Asynchronous Experiment Execution

Requirement:
The system shall execute experiments asynchronously.

Preconditions:
- Experiment exists.
- Caller has execution permission.
- Dataset version is valid.
- Target version is immutable.

Failure behavior:
- Queue unavailable -> return retryable failure.
- Target unavailable -> execution enters retry policy.
- Invalid experiment -> execution must not be queued.

Tests:
- Unit
- Integration
- Load
- Manual
```

## Functional Requirement Areas

The following sections list the known functional requirement areas of AEGIS. Each entry is a placeholder. Every placeholder must be authored using the full 15-attribute template above before it is considered a requirement.

### FR-PRJ: Projects

Project management, organization hierarchy, tenancy, and role-based access control.

- `FR-PRJ-01` — Create project.
- `FR-PRJ-02` — List projects within organization.
- `FR-PRJ-03` — Assign roles and permissions.
- `FR-PRJ-04` — Service account management.

### FR-TGT: Targets and Target Versions

Registration of AI systems, immutable version snapshots, and integration mode support.

- `FR-TGT-01` — Register a target.
- `FR-TGT-02` — Create immutable target version.
- `FR-TGT-03` — Record code commit, container digest, model version.
- `FR-TGT-04` — Support black-box HTTP, SDK, OpenTelemetry, webhook, and CI integration modes.

### FR-DAT: Datasets and Test Cases

Versioned collections of evaluation scenarios including normal, adversarial, and edge cases.

- `FR-DAT-01` — Create versioned dataset.
- `FR-DAT-02` — Add test cases with golden data, expected tool calls, conversation history, and memory state.
- `FR-DAT-03` — Detect duplicates, near-duplicates, and class imbalance.
- `FR-DAT-04` — Support dataset slices for subgroup analysis.
- `FR-DAT-05` — Promote production failures to regression tests under approval.

### FR-EXP: Experiments and Variants

Reproducible evaluation configurations executed against target versions, with variant comparison.

- `FR-EXP-01` — Create experiment with target, dataset, evaluators, and policies.
- `FR-EXP-02` — Support experiment variants for A/B and pairwise comparison.
- `FR-EXP-03` — Enforce immutability of running and historical experiments.
- `FR-EXP-04` — Support configurable evaluation caching with invalidation on prompt or model version change.

### FR-EXE: Execution, Retry, and Cancellation

Asynchronous execution of experiments with bounded retry, timeout, and cancellation.

- `FR-EXE-01` — Execute experiments asynchronously.
- `FR-EXE-02` — Bounded retry with exponential backoff and error classification.
- `FR-EXE-03` — Mandatory per-target, per-test, and overall experiment timeouts.
- `FR-EXE-04` — Cooperative cancellation plus hard timeout.
- `FR-EXE-05` — Idempotent jobs to prevent duplicate side effects.
- `FR-EXE-06` — Rate limiting on target invocations.
- `FR-EXE-07` — Tool side effects disabled or sandboxed by default.

### FR-TRC: Tracing

OpenTelemetry-compatible trace collection with configurable content capture.

- `FR-TRC-01` — Collect traces for model calls, retrieval, tools, memory, guardrails, and agent execution.
- `FR-TRC-02` — Store structured spans with AI-specific semantic attributes.
- `FR-TRC-03` — Configurable prompt and output capture for privacy.
- `FR-TRC-04` — PII redaction before storage.
- `FR-TRC-05` — Secret detection in model outputs.
- `FR-TRC-06` — Token usage, latency, time-to-first-token, and cost tracing.
- `FR-TRC-07` — Link traces to evaluation results and incidents.

### FR-EVL: Evaluation and Evaluators

Plugin-based evaluator architecture supporting deterministic, semantic, and LLM-as-judge metrics.

- `FR-EVL-01` — Execute evaluator plugins via isolated RPC-evaluator interface.
- `FR-EVL-02` — Version evaluators, judge models, and judge prompts.
- `FR-EVL-03` — Store structured rationale and evidence with every metric result.
- `FR-EVL-04` — Normalize scores across metric types while preserving native semantics.
- `FR-EVL-05` — Support configurable thresholds per metric with severity classification.
- `FR-EVL-06` — Detect flaky metrics through repeated evaluation variance analysis.
- `FR-EVL-07` — Separate deterministic, semantic, and LLM-as-judge metric categories.

### FR-ANA: Analysis and Regression

Per-test and aggregate comparison, failure clustering, and statistical significance testing.

- `FR-ANA-01` — Compare metrics across target versions.
- `FR-ANA-02` — Per-test regression detection.
- `FR-ANA-03` — Failure classification and clustering.
- `FR-ANA-04` — Confidence intervals and statistical significance where sample sizes permit.
- `FR-ANA-05` — Slice-level analysis for subgroup regression detection.

### FR-POL: Policies and Gates

Versioned guardrail policies, blocking and advisory metrics, and deployment gates with composite logic.

- `FR-POL-01` — Define and version guardrail policies.
- `FR-POL-02` — Policy composition with boolean logic.
- `FR-POL-03` — Non-compensatory policy: safety failure cannot be overridden by quality improvement.
- `FR-POL-04` — Deployment gates with configurable pass, warn, block, and human override.
- `FR-POL-05` — Policy failure triggers regression test suite.
- `FR-POL-06` — Gate test selection based on dependency graph and affected components.

### FR-EVD: Evidence

Evidence graph linking experiment, dataset version, target version, execution, evaluators, and results.

- `FR-EVD-01` — Build evidence graph for every experiment.
- `FR-EVD-02` — Link every score to dataset version, target version, evaluator version, and judge model.
- `FR-EVD-03` — Preserve execution trace, tool calls, retrieval events, memory events, and errors.
- `FR-EVD-04` — Store provenance: metric source, algorithm, assumptions, and limitations.

### FR-SEC: Security

Red-team evaluation, threat taxonomy integration, and controlled attack execution.

- `FR-SEC-01` — Execute red-team tests driven by threat models and known attack classes.
- `FR-SEC-02` — Mandatory prompt injection, sensitive information disclosure, tool misuse, identity abuse, memory poisoning, and excessive agency tests.
- `FR-SEC-03` — Custom attack creation with secure payload storage.
- `FR-SEC-04` — Simulation mode with side effects blocked or sandboxed.
- `FR-SEC-05` — Red-team data access restricted by authorization.

### FR-OBS: Observability

Production observability with OpenTelemetry-compatible semantics and AI-specific semantic context.

- `FR-OBS-01` — OpenTelemetry-compatible trace ingestion from production targets.
- `FR-OBS-02` — Sampling support for production telemetry.
- `FR-OBS-03` — Evaluation traces normally not sampled.
- `FR-OBS-04` — Provider pricing versioning for accurate cost tracking.
- `FR-OBS-05` — Data classification enforcement (public, internal, confidential, restricted, regulated).

---

**Reminder**: Every placeholder above must be authored with the full 15-attribute template before it is considered a requirement. No requirement is complete without a test strategy.
