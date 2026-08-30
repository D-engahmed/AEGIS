# Test Data Strategy

## Purpose

Evaluation quality is bounded by test-set quality. AEGIS produces scores, and a score is only as meaningful as the data it was computed from. The test data strategy defines the composition, quality, governance, and environment of that data. Bad datasets produce good-looking scores easily, so the datasets themselves are validated before they are trusted.

## Test Data Composition

Test data exists on a spectrum from normal through pathological. Coverage must include all of it:

- **Realistic**: representative production-like scenarios with real-world phrasing and structure.
- **Adversarial**: prompt injection, indirect injection through tool results and retrieved content, memory poisoning, tool abuse, excessive agency attempts.
- **Edge and invalid inputs**: malformed JSON where structured input is expected, empty input, very long input, nonsensical input ("asdfghjkl"), ambiguous and contradictory requests, missing information, out-of-domain and high-risk requests.

The input robustness matrix governs coverage: every target type (LLM, RAG, agent, memory, tools, guardrails) is tested under normal, ambiguous, malformed, and adversarial inputs.

Test cases may carry expected output, expected tool calls, expected retrieval evidence, conversation history, memory state, and controlled environment state. A golden is the expected or reference information used to construct or evaluate a test; not every test needs a golden answer, because some evaluations are referenceless.

## Golden Datasets for Evaluator Calibration

Known-good and known-bad calibration examples calibrate evaluators:

- Known-good examples have a labeled correct verdict; the evaluator must not false-negative on them.
- Known-bad examples have a labeled expected failure; the evaluator must not false-positive on them.
- The evaluator's own accuracy, precision, and recall are measured on the golden dataset, and a judge that drifts from calibrated accuracy is flagged.
- Golden datasets also calibrate LLM judges through human agreement analysis, so automated evaluation does not trust its own claim.

## Dataset Quality Checks

Datasets are quality-checked before they are used for verdicts:

- **Duplicates**: identical test cases inflate scores and hide coverage gaps.
- **Near-duplicates**: a model can appear strong by repeatedly seeing similar scenarios; near-duplicates are detected and reported.
- **Leakage and contamination**: test cases that overlap training data or evaluation goldens are flagged where feasible. AEGIS cannot prove absence of contamination, so it reports what it finds and is honest about what it cannot prove.
- **Class imbalance**: skewed label or slice distributions that would bias aggregate scores.
- **Ambiguity and invalid references**: test cases that cannot be scored deterministically or reference missing artifacts.
- **Coverage**: the composition above — realistic, adversarial, edge, invalid — is effectively represented.

Recent research guidance and DeepEval's dataset guidance emphasize diverse real-world inputs, complexity variation, and edge cases; AEGIS encodes that as explicit quality gates on datasets rather than preference.

## Public vs Private Datasets

Public and private dataset classes prevent overfitting to known test cases:

- Public datasets are visible to teams and used for development and iteration.
- Private (hidden) test sets are used for high-stakes benchmarks and evaluation; developers cannot optimize against known test cases because they cannot see them.
- Hidden test sets are the evidence against gamesmanship: a score earned on a set the developer has never seen is the meaningful one.

## Synthetic Data

Synthetic data provides coverage; it never replaces realism:

- Synthetic cases deliberately exercise edge, invalid, and adversarial conditions that are rare in real traffic.
- Real data provides the realism that synthetic data cannot: natural language variance, real retrieval distributions, real failure modes.
- Production traces become evaluation cases only under privacy and approval policies; they are not harvested automatically.

## Recorded Provider Responses as Fixtures

Integration and end-to-end tests use recorded provider responses as fixtures, so no real LLM is invoked in unit or integration tests unless explicitly tagged:

- Response recordings are deterministic fixtures served from disk, eliminating provider cost, network, and nondeterminism from the suite.
- Real-model behavior is reserved for explicitly tagged suites and scheduled runs, never the default test path.
- Recordings must be labeled with the provider, model, and configuration that produced them so the fixture's provenance is preserved.

## Data Classification and Privacy

Test data must not contain real secrets or PII:

- Synthetic and seeded values are used for credential-like and PII-like content; real credentials never enter test data.
- Data classification (public, internal, confidential, restricted, regulated) governs who can access a dataset and how long it is retained.
- Secret-like patterns in test outputs are detections to test against, not values to store; PII is synthetic by construction.

## Seeded Deterministic Data for Repeatability

Tests run against seeded, deterministic data so runs are reproducible:

- Seed values are fixed and versioned with the dataset and environment.
- A reproducible run uses the same dataset version, target version, evaluator version, and seed; reproducibility is verified against the `NFR-REPRO-01` envelope.
- Unless a test is explicitly tagged otherwise, running it twice produces the same inputs and, within stochastic tolerance, the same verdicts.