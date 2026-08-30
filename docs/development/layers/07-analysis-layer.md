# Layer 07: Analysis

## 1. Purpose

The analysis layer interprets evaluation results to produce regression detection, failure clustering, comparison, slicing, and statistical significance analysis. It is explicitly separated from evaluation: evaluation says "what happened?" and analysis says "did it change?"

## 2. Responsibilities

- Regression detection (comparing current results against baseline).
- Failure clustering and classification (grouping failures by root cause category).
- Experiment comparison (A/B evaluation, pairwise comparison).
- Dataset slicing (per-category, per-language, per-risk-level analysis).
- Statistical significance testing (confidence intervals, p-values where sample sizes permit).
- Trend analysis over time.

## 3. Non-Responsibilities

- Computing metric scores (evaluation layer).
- Making pass/warn/block decisions (policy and gates layer).
- Persisting evidence (evidence layer).
- Scheduling or running evaluations (execution layer).

## 4. Public Interfaces

Analysis reports, regression alerts, failure cluster summaries, and comparison results. These are consumed by the interface layer (for dashboards) and the policy and gates layer (for gate decisions).

## 5. Inputs

MetricResult objects from the evaluation layer, historical result sets, and analysis configuration (comparison baselines, significance thresholds).

## 6. Outputs

RegressionReport, FailureClusterReport, ComparisonReport, SliceReport, and TrendReport.

## 7. Internal Components

- Regression detector (delta calculation, significance testing).
- Failure classifier (categorizing failures by type: model, retrieval, tool, timeout, validation).
- Failure clusterer (grouping similar failures for actionable reporting).
- Comparison engine (A/B, pairwise, multi-variant).
- Slicer (per-dimension analysis: language, risk level, task type, input length).
- Statistical calculator (confidence intervals, effect size, power analysis).

## 8. Allowed Dependencies

- Application layer (02) for configuration and orchestration interfaces.
- Domain layer (01) for entity types and invariants.
- Statistical libraries (scipy, numpy) as justified in dependency-rules.md.

## 9. Forbidden Dependencies

- Interface layer (03) -- analysis does not handle HTTP.
- Execution layer (05) -- analysis does not schedule work.
- Evaluation layer (06) -- analysis interprets results, it does not compute them.
- Infrastructure layer (04) -- analysis reads through repository interfaces.

## 10. Why This Design

Evaluation and analysis answer different questions. Evaluation produces scores; analysis interprets what those scores mean in context. Separating them prevents analysis logic from contaminating metric computation and allows each to evolve independently.

## 11. Alternatives Considered

- **Merged evaluation and analysis**: Rejected because it conflates measurement with interpretation.
- **Analysis as a dashboard-only concern**: Rejected because analysis results drive gate decisions programmatically.
- **Real-time analysis inline with evaluation**: Rejected because analysis requires historical context that is not available during single-run evaluation.

## 12. Why Alternatives Were Rejected

Merging conflates distinct responsibilities. Dashboard-only placement prevents programmatic gate driving. Inline analysis lacks historical context.

## 13. Technology Choice

Python with numpy and scipy for statistical computation. No heavy ML frameworks required for MVP analysis.

## 14. Technology Limits

Statistical significance requires sufficient sample sizes. Small datasets produce unreliable regression signals. Clustering quality depends on failure classification completeness.

## 15. When To Use This Technology

After evaluation runs complete. When comparing experiments. When investigating failure patterns. When slicing results by dimension.

## 16. When NOT To Use This Technology

During evaluation (use evaluation layer). During gate decisions (use policy and gates layer, but analysis results feed into it).

## 17. Failure Modes

- False regression alerts from statistically insignificant deltas.
- Failure clusters that are too broad to be actionable.
- Comparison across different evaluator versions producing misleading results.
- Slicing by dimensions with insufficient sample size producing unreliable signals.

## 18. Security Risks

- Analysis reports exposing sensitive evaluation data to unauthorized consumers.
- Failure cluster details revealing proprietary model behavior.
- Historical trend data retained beyond retention policy.

## 19. Performance Risks

- Large-scale comparison across thousands of experiments being computationally expensive.
- Statistical computation on high-dimensional slicing being slow.
- Memory pressure from loading full historical result sets for trend analysis.

## 20. Testing Strategy

Unit tests with synthetic data covering known regression, improvement, and no-change scenarios. Tests for statistical significance with varying sample sizes. Tests for failure classification accuracy.

## 21. Scaling Strategy

Incremental analysis (compute deltas against previous runs, not full history). Materialized analysis results for dashboard queries. Background computation for trend analysis.

## 22. Agent Rules

Before writing analysis code: confirm it interprets existing results, not computes new metrics. After writing: verify that analysis results reference the evaluator versions and configurations they were derived from.

## 23. Code Examples

Analysis example with verbatim format:

```
Evaluator:
Faithfulness = 0.72

Analysis:
Previous = 0.91
Current = 0.72
Delta = -0.19
Confidence = 95%
Regression = Significant
```

## 24. Common Implementation Mistakes

- Treating analysis as a subset of evaluation instead of a separate concern.
- Not tracking evaluator version across comparison baselines.
- Reporting average scores across all slices, hiding per-slice regressions.
- Using inappropriate statistical tests for the data distribution.
- Not flagging results where sample size is too small for significance.
- Mixing analysis and policy logic (analysis reports; policy decides).
