# Layer 09: Evidence

## 1. Purpose

The evidence layer is not just a database layer. It establishes the provenance, traceability, and reproducibility of every score AEGIS produces. Central rule: no score without evidence.

## 2. Responsibilities

- Provenance tracking (who/what produced this result, with which configuration).
- Traceability (linking results back to executions, evaluators, datasets, and target versions).
- Artifact reference management (storing references to traces, logs, and large payloads).
- Evidence linking (connecting results to the evidence graph).
- Reproducibility support (recording all versioned inputs that produced a result).
- Immutable record maintenance (historical results are never modified).

## 3. Non-Responsibilities

- Computing metric scores (evaluation layer).
- Interpreting results (analysis layer).
- Making gate decisions (policy and gates layer).
- Job scheduling (execution layer).

## 4. Public Interfaces

Evidence repository (store, retrieve, link), provenance query API, and evidence graph query interface.

## 5. Inputs

MetricResult objects, execution traces, evaluator metadata, experiment configurations, and dataset versions.

## 6. Outputs

Immutable evidence records, provenance links, and evidence graph queries for dashboards and audit.

## 7. Internal Components

- Evidence record storage (relational for metadata, object storage for large payloads).
- Provenance linker (connecting results to their generating configuration).
- Evidence graph builder and query engine.
- Artifact reference manager (links to traces, logs, reports in object storage).
- Immutability enforcer (append-only for historical records).

## 8. Allowed Dependencies

- Domain layer (01) for entity types.
- Infrastructure layer (04) for storage adapters.
- Application layer (02) for configuration.

## 9. Forbidden Dependencies

- Evaluation layer (06) -- evidence stores results, it does not compute them.
- Interface layer (03) -- evidence has no HTTP awareness.
- Execution layer (05) -- evidence does not schedule work.

## 10. Why This Design

Without evidence, scores are unverifiable assertions. The evidence layer ensures that every score can be traced back to the exact configuration, execution, and evaluator that produced it. This is what distinguishes AEGIS from a dashboard that displays numbers.

## 11. Alternatives Considered

- **Evidence as database tables only**: Rejected because large artifacts (traces, reports) require object storage references.
- **Evidence as a logging system**: Rejected because evidence requires structured querying and graph relationships.
- **Evidence computed inline with evaluation**: Rejected because evidence persistence must be durable and independent of evaluation runtime.

## 12. Why Alternatives Were Rejected

Database-only is insufficient for large payloads. Logging lacks query capability. Inline persistence risks data loss on evaluation failure.

## 13. Technology Choice

PostgreSQL for relational evidence metadata. Object storage (S3-compatible) for large artifacts. In-memory graph for evidence relationships (materialized in database for persistence).

## 14. Technology Limits

Evidence graph query complexity grows with the number of linked entities. Large trace payloads may exceed storage limits without proper lifecycle management.

## 15. When To Use This Technology

Every evaluation result, every execution trace, every experiment verdict. No score is persisted without its evidence.

## 16. When NOT To Use This Technology

Real-time metric computation (use evaluation layer). Analysis interpretation (use analysis layer). Gate decisions (use policy and gates layer).

## 17. Failure Modes

- Evidence record creation failure after metric computation, leaving scores without evidence.
- Provenance links pointing to outdated or deleted configurations.
- Evidence graph becoming inconsistent after partial failures.
- Object storage outages preventing artifact retrieval.
- Immutability violation from code bugs that modify historical records.

## 18. Security Risks

- Evidence records containing PII or secrets without redaction.
- Unauthorized access to evidence graph revealing proprietary AI behavior.
- Evidence tampering (mitigated by immutability enforcement).
- Large trace payloads containing sensitive data without retention limits.

## 19. Performance Risks

- Evidence graph queries becoming slow with large datasets.
- Object storage latency affecting dashboard load times.
- Concurrent evidence writes creating contention.
- Evidence cleanup and archival impacting query performance.

## 20. Testing Strategy

Unit tests for provenance linking accuracy. Integration tests for evidence persistence and retrieval. Immutability tests verifying historical records cannot be modified. Evidence graph consistency tests.

## 21. Scaling Strategy

Evidence metadata scales with PostgreSQL partitioning. Large artifacts scale with object storage. Evidence graph can be materialized and indexed for query performance.

## 22. Agent Rules

Before writing evidence code: confirm it persists and links evidence, not computes results. After writing: verify that every score path includes evidence creation and that no historical record is modifiable.

## 23. Code Examples

Evidence graph structure:

```
Experiment
    │
    ├── Dataset Version
    │
    ├── Target Version
    │      ├── Code Version
    │      ├── Model Version
    │      ├── Prompt Version
    │      ├── RAG Version
    │      ├── Memory Policy
    │      └── Guardrail Policy
    │
    ├── Execution
    │      ├── Trace
    │      ├── Tool Calls
    │      ├── Retrieval
    │      ├── Memory Events
    │      └── Errors
    │
    ├── Evaluators
    │      ├── Metric Version
    │      ├── Judge Model
    │      └── Judge Prompt
    │
    └── Results
           ├── Scores
           ├── Evidence
           ├── Failures
           ├── Regression
           └── Verdict
```

## 24. Common Implementation Mistakes

- Storing scores without evidence references.
- Allowing evidence records to be updated after creation.
- Not linking results to evaluator version and configuration.
- Storing large trace payloads in the relational database instead of object storage.
- Missing artifact cleanup for expired evidence.
- Evidence graph links pointing to deleted or non-existent entities.
- Evidence creation not atomic with result persistence, leading to orphaned scores.
