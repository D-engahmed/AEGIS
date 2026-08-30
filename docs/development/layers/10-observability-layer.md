# Layer 10: Observability

## 1. Purpose

The observability layer monitors two things: AEGIS evaluating other systems, and AEGIS itself. It provides the telemetry, tracing, and metrics needed to understand system health, evaluation performance, and AI behavior.

## 2. Responsibilities

- Monitoring AEGIS evaluating other systems (evaluation traces, evaluator performance, cost).
- Monitoring AEGIS itself (worker latency, queue depth, evaluator failures, API latency, database health).
- Trace ingestion from target AI systems (OpenTelemetry-compatible).
- Metric collection and export (OpenTelemetry metrics).
- Structured logging with correlation IDs.
- Evaluation trace preservation (traces are evidence and are NOT sampled away).

## 3. Non-Responsibilities

- Business logic and domain rules (domain layer).
- Metric computation for evaluation purposes (evaluation layer).
- Gate decisions (policy and gates layer).
- Evidence persistence beyond telemetry (evidence layer).

## 4. Public Interfaces

Telemetry exporter interfaces, trace query API, and metric query API. These are consumed by the interface layer (for dashboards) and by external observability platforms (Grafana, Datadog, etc.).

## 5. Inputs

Traces from target AI systems, internal metrics from all AEGIS layers, and health check signals.

## 6. Outputs

Exported traces (OpenTelemetry format), exported metrics, structured logs, and observability dashboards.

## 7. Internal Components

- OpenTelemetry trace exporter.
- OpenTelemetry metric exporter.
- Structured log formatter with correlation ID injection.
- Health check aggregator.
- Cost tracker (evaluator cost vs. target cost).
- Trace preservation engine (ensuring evaluation traces are retained as evidence).

## 8. Allowed Dependencies

- OpenTelemetry SDK (tracing, metrics).
- Application layer (02) for configuration.
- Domain layer (01) for entity types.

## 9. Forbidden Dependencies

- Interface layer (03) -- observability does not handle HTTP requests.
- Execution layer (05) -- observability does not schedule work.
- Evaluation layer (06) -- observability monitors evaluation, it does not perform it.
- Infrastructure layer (04) -- observability uses its own telemetry infrastructure.

## 10. Why This Design

Observability is cross-cutting but must be explicitly designed. Without a dedicated layer, observability concerns are scattered across the codebase and inconsistently implemented. A dedicated layer ensures telemetry is comprehensive, consistent, and integrated.

## 11. Alternatives Considered

- **Observability as middleware only**: Rejected because it misses background job telemetry and evaluation trace preservation.
- **Third-party observability platform as the only solution**: Rejected because AEGIS needs to own evaluation traces as evidence, not just forward them.
- **Inline logging in each layer**: Rejected because it produces inconsistent formats and misses cross-cutting concerns.

## 12. Why Alternatives Were Rejected

Middleware-only misses non-HTTP telemetry. Third-party platforms do not preserve evaluation traces as evidence. Inline logging is inconsistent.

## 13. Technology Choice

OpenTelemetry SDK for traces and metrics. Structured logging (JSON format) with correlation IDs. Compatible with Grafana, Datadog, and other OTel-compatible backends.

## 14. Technology Limits

OpenTelemetry semantic conventions for AI-specific concepts are still evolving. Custom span attributes may be needed for AI-specific telemetry. Evaluation trace volume can be high.

## 15. When To Use This Technology

Every API request, every background job execution, every evaluation run, every target call, and every system health event.

## 16. When NOT To Use This Technology

Business logic, metric computation, gate decisions, and evidence persistence beyond telemetry scope.

## 17. Failure Modes

- Telemetry exporter failures causing application slowdowns (must degrade gracefully).
- Evaluation traces sampled away, losing evidence.
- Correlation IDs lost across async boundaries.
- Cost tracking inaccurate due to provider pricing changes.
- Metric cardinality explosion from unbounded label values.

## 18. Security Risks

- Telemetry data containing PII or secrets without redaction.
- Trace export endpoints exposed without authentication.
- Internal system topology revealed through trace data.
- Cost data exposed to unauthorized users.

## 19. Performance Risks

- Telemetry export blocking application threads.
- High trace volume from evaluation runs overwhelming storage.
- Metric cardinality explosion increasing memory and storage costs.
- Synchronous logging slowing request handling.

## 20. Testing Strategy

Unit tests for trace export and metric collection. Integration tests for correlation ID propagation. Tests verifying evaluation traces are preserved (not sampled). Tests for PII redaction in telemetry.

## 21. Scaling Strategy

Async telemetry export. Trace sampling for production observability (but NOT for evaluation traces). Metric aggregation at export time. Log rotation and retention policies.

## 22. Agent Rules

Before writing observability code: confirm it adds telemetry without introducing business logic. After writing: verify evaluation traces are preserved as evidence, not sampled away, and that no PII or secrets appear in telemetry data.

## 23. Code Examples

Monitored signals:

```
Worker latency
Queue depth
Evaluator failures
Cost
API latency
Database health
Trace ingestion
```

Evaluation traces are evidence and are NOT sampled away.

## 24. Common Implementation Mistakes

- Sampling evaluation traces, losing evidence.
- Missing correlation IDs across async job boundaries.
- Logging PII or secrets in telemetry data.
- Blocking on telemetry export instead of async.
- Not tracking evaluator cost separately from target cost.
- Inconsistent metric naming across layers.
- Missing health checks for critical dependencies.
- Telemetry exporter errors not handled gracefully.
