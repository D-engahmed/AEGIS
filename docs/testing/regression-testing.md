# Regression Testing

## Purpose

Regression testing is the reason AEGIS tracks target versions at all: is this AI system getting worse over time? The regression discipline decides what counts as "worse," which comparisons are informative, and how failures become permanent guards.

Regression analysis in AEGIS is supported by the analysis layer (`docs/architecture/` analysis engine: regression, failure, comparison, slicing, statistics). The testing side defines the rules and the data the analysis runs on.

## Per-Test Comparison Over Aggregates

Per-test comparison of two versions of a target across the same dataset slice is more informative than aggregate scores. An aggregate moved from 87% to 91% looks like an improvement; the per-test view shows which individual cases regressed while the aggregate improved. A regression is a case-level fact:

```text
Test #184

v0.3:
SUCCESS

v0.4:
FAILED

Regression Detected
```

Regression detection works per test case first, then aggregates and slices over those cases. Never declare a clean regression report from aggregates alone.

## Statistical Significance

Regression detection needs sample sizes and statistical significance. A 1% improvement is not automatically meaningful; sampling noise may exceed the improvement (`grilling.md`). Regression verdicts must account for:

- **Sample size**: regressions on a single test case are real facts about that case; regressions on a slice or aggregate need enough cases to be significant.
- **Confidence intervals**: scores carry uncertainty, and comparisons must respect it.
- **Repeated evaluation**: variance analysis identifies flaky metrics; a flaky metric must not block by default.

The analysis layer computes significance; regression reporting must present it, not hide it.

## Non-Compensatory Rules for Safety Regressions

Some dimensions are non-compensatory. A quality improvement never compensates for a safety regression: a critical safety failure is a block regardless of how much helpfulness improved. This applies to regression verdicts exactly as it applies to gates:

- Safety regressions are evaluated independently of quality, cost, and latency.
- A safety regression blocks; an aggregate improvement elsewhere does not dilute it.
- Policy configures which metrics are non-compensatory and which are advisory.

## Failed Tests Are Proposed for Promotion, Not Silently Promoted

A failed test may be an invalid expectation rather than a system defect. Production traces and manual curation identify failure cases, but promotion to the regression suite is always a proposal with human review:

- A case that regressed is proposed for promotion to a regression suite.
- The proposal carries the evidence, the failure classification, and the suspected cause.
- Promotion is approved when the expectation is confirmed valid; a test that encodes a wrong expectation is fixed or rejected, never blindly promoted.
- No case is silently added to a regression suite by automation alone.

## Sliced Regression Reporting

Aggregate scores hide subgroup failures. Regression reporting slices by dataset labels and dimensions:

```text
billing
Arabic
tool-use
safety
edge-case
long-context
high-risk actions
```

A regression that only appears on one slice (for example, Arabic-language queries or long-context cases) must be reported on that slice, even when the aggregate looks unchanged.

## Tagging for Dependency-Aware Selection

Regression suites are tagged so the right suite runs when the corresponding component changes. Selection is governed by the dependency graph and the CI/CD gates (`docs/ci-cd/pull-request-gates.md`):

| Change | Suite That Runs |
|---|---|
| Prompt change | Language and quality regression suites |
| Model change | Regression suite |
| Retriever change | RAG regression suite |
| Tool schema change | Agent and tool regression suites |
| Guardrail change | Safety regression suite |
| Memory policy change | Memory regression suite |

The smoke suite runs on every change; expensive regression suites are scheduled per the tag configuration. Running the wrong subset is prevented by mapping changes to their dependent suites at selection time.