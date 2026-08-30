# Evidence Architecture

The Evidence Plane is not a database layer. It is the foundation of AEGIS's trustworthiness. Every score, every verdict, every regression signal must be explainable by the evidence that produced it. Without evidence, a number is a claim; with evidence, a number is a fact that engineers can verify.

```text
"No score without evidence."
```

---

## Responsibilities

The Evidence Plane owns five responsibilities:

### Provenance

Every evaluation outcome traces back to the exact inputs, versions, and configuration that produced it. Provenance answers the question: "What, precisely, produced this score?" It encompasses the target version, the model, the prompt, the dataset version, the evaluator, the judge model, and all configuration parameters.

### Traceability

Every entity in the system can be followed forward and backward through its relationships. From a verdict, one can reach the experiment, the execution, the trace, the evidence, and the underlying configuration. From a configuration version, one can reach every experiment and result that used it.

### Artifact References

Large payloads live in object storage and are referenced by stable keys, not embedded in the evidence graph. Traces, datasets, and reports are stored as artifacts. The evidence graph stores references to these artifacts so it remains compact and queryable while preserving access to the full data.

### Evidence Linking

A score links to the exact evidence that produced it. The link contains the evaluator result, the underlying trace artifact, the test case input, and the expected outcome. This makes it possible to reproduce the score by replaying the same inputs through the same configuration.

### Reproducibility

Given the same dataset version, target version, and evaluator versions, an evaluation should produce the same result to the extent that stochastic AI permits. Reproducibility requires versioning everything that can affect the outcome.

---

## The Fundamental Rule

```text
"No score without evidence."
```

This rule is enforced at the write boundary. A Result cannot be created unless it references:

```text
A Result cannot exist without:

Experiment
Target Version
Dataset Version
Evaluator Version
Execution
Evidence
```

The evidence graph enforces this invariant. Any attempt to create a score without its supporting evidence is rejected.

---

## The Evidence Graph

```text
Experiment
    |
    |-- Dataset Version
    |
    |-- Target Version
    |      |-- Code Version
    |      |-- Model Version
    |      |-- Prompt Version
    |      |-- RAG Configuration
    |      |-- Memory Policy
    |      |-- Guardrail Policy
    |
    |-- Execution
    |      |-- Trace
    |      |-- Tool Calls
    |      |-- Retrieval
    |      |-- Memory Events
    |      |-- Errors
    |
    |-- Evaluators
    |      |-- Metric Version
    |      |-- Judge Model
    |      |-- Judge Prompt
    |
    +-- Results
           |-- Scores
           |-- Evidence
           |-- Failures
           |-- Regression
           +-- Verdict
```

The graph is a directed acyclic structure rooted at the Experiment. Each node records the precise identity and version of the configuration or outcome it represents.

### Experiment

The root node. References the dataset version and the target version being evaluated, and the set of evaluators and policies attached to the run.

### Dataset Version

The immutable snapshot of the test scenarios. References the locked dataset version ID.

### Target Version

The reproducible configuration of the AI system under test. It captures:

- **Code version**: Source commit / build identity.
- **Model version**: Model digest or provider model version where available.
- **Prompt version**: The exact prompt and its version.
- **RAG configuration**: Retrieval strategy, top-k, chunking, embedding model.
- **Memory policy**: The memory configuration and policy governing persistent state.
- **Guardrail policy**: The guardrail controls and their version.

Secrets never enter the evaluation record or the target metadata.

### Execution

The record of a single invocation of a target against a test case. It captures the trace (the full span tree), tool calls with arguments and results, retrieval events, memory events, errors, timing, token usage, and cost.

### Evaluators

The versioned evaluation configuration applied to the execution. Captures the metric/plugin version, the judge model, and the judge prompt version. An evaluator is itself a versioned AI dependency (grilling.md).

### Results

The terminal scores and outcomes. Each result references:

- **Scores**: The normalized score value.
- **Evidence**: References to the underlying evidence that produced the score.
- **Failures**: Failed assertions or criteria.
- **Regression**: Regression signals against a baseline.
- **Verdict**: The final gate conclusion (pass, warn, block, human override).

---

## Result Composition

Every result carries its provenance metadata:

```text
Result
|-- evaluator_identity
|-- evaluator_version
|-- judge_model
|-- judge_prompt_version
|-- confidence
|-- evidence_references
|   |-- trace_artifact_id
|   |-- dataset_case_id
|   +-- execution_id
+-- score
```

The evaluator identity and version identify the exact evaluator configuration. The judge model and judge prompt version identify the exact LLM judge dependency. Confidence reflects the reliability of the score (low for ambiguous judgments, high for deterministic checks). Evidence references link the score to the exact trace and artifact that produced it.

This prevents the common failure mode of a score being displayed without any way to verify it. Every number in the UI carries its complete provenance.

---

## Reproducibility

Version everything possible (grilling.md, question 48):

```text
model
prompt
evaluator
dataset
configuration
seed
environment
target version
```

AEGIS records all of these at the point of evaluation. When an engineer re-runs an experiment:

- The target version resolves to the exact code, model, prompt, and configuration.
- The dataset version resolves to the exact locked test cases.
- The evaluator version resolves to the exact metric, judge model, and judge prompt.
- The environment and seed (where supported) capture stochastic parameters.
- The captured trace and artifacts allow replay against mocks and snapshots.

Reproducibility is as faithful as stochastic AI permits. AEGIS does not pretend that stochastic evaluation is deterministic; it captures the stochastic parameters so the conditions are known.

---

## Artifact References

Artifacts are stored in object storage and referenced by stable keys:

- **Traces**: Full trace payloads, keyed by execution ID.
- **Datasets**: Dataset files and test case payloads, keyed by dataset version.
- **Reports**: Generated reports, keyed by experiment and report version.
- **Attack payloads**: Red-team and adversarial payloads, stored securely and keyed for restricted access.

The evidence graph stores the artifact keys, not the artifact content. This keeps the graph small and queryable while preserving full fidelity on demand.

---

## Trustworthiness Guarantees

Evidence is trustworthy only if it cannot be silently altered or removed while still in force.

### Immutability

Evidence records are immutable after publication. Traces, executions, evaluator results, and evidence references are written once and never updated. There is no update path for evidence records in the schema.

### Retention

Evidence is retained until the applicable policy expiry. Retention is configurable per data classification and per organization. Evidence referenced by a gate verdict or an active policy is retained until that policy expires or the experiment is explicitly retired.

Evidence that must be removed for privacy or regulatory reasons goes through a controlled deletion process. Deletion is audit-logged and recorded in the system.

### Reference

- ADR-005: Evidence graph and provenance model (docs/architecture/architecture-decision-records/)
