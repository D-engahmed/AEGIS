# Non-Functional Requirements

## How NFRs Are Authored

Vague statements like "The system should be fast" are not acceptable. Every NFR must contain the following eight attributes. No attribute may be omitted.

```text
Metric
Measurement Method
Target
Environment
Failure Threshold
Monitoring Method
Test Method
Priority
```

## Measurement Notes

- Percentiles used throughout: **p50**, **p95**, **p99**.
- API latency measurements **exclude** asynchronous experiment execution. Experiment execution latency is measured separately.
- All measurements must be reproducible in the stated environment.

## Worked Example

```text
NFR-PERF-01

Metric:
API p95 latency.

Measurement Method:
HTTP request timing from API gateway to response completion.

Target:
< 500ms.

Environment:
Production-equivalent staging with representative dataset sizes.

Failure Threshold:
p95 exceeds 500ms for 5 consecutive minutes.

Monitoring Method:
Continuous latency monitoring with percentile dashboards.

Test Method:
Automated load test suite, manual baseline verification.

Priority:
High.
```

---

## NFR Templates by Area

### Performance / Latency

```text
NFR-PERF-02

Metric:
Trace ingestion p95 latency.

Measurement Method:
Trace payload receipt to persistence confirmation.

Target:
< 200ms for payloads under 1MB.

Environment:
Production-equivalent staging.

Failure Threshold:
p95 exceeds 200ms for 5 consecutive minutes.

Monitoring Method:
Ingestion pipeline latency monitoring.

Test Method:
Automated load test, manual verification with large payloads.

Priority:
High.
```

```text
NFR-PERF-03

Metric:
Evaluation result query p95 latency.

Measurement Method:
API request timing for evaluation result retrieval.

Target:
< 300ms for result sets under 10,000 records.

Environment:
Production-equivalent staging with representative data volumes.

Failure Threshold:
p95 exceeds 300ms for 5 consecutive minutes.

Monitoring Method:
Query latency monitoring with slow query logging.

Test Method:
Automated query performance test suite.

Priority:
Medium.
```

### Throughput

```text
NFR-PERF-04

Metric:
Experiment execution throughput.

Measurement Method:
Concurrent experiment runs completed per minute.

Target:
>= 50 concurrent experiment runs with 100 test cases each.

Environment:
Production-equivalent staging with 4 worker nodes.

Failure Threshold:
Throughput drops below 30 concurrent runs.

Monitoring Method:
Worker utilization and queue depth monitoring.

Test Method:
Load test with graduated concurrency.

Priority:
High.
```

### Availability

```text
NFR-AVAIL-01

Metric:
API availability.

Measurement Method:
Successful HTTP responses (2xx/3xx) divided by total requests.

Target:
>= 99.5% uptime per calendar month.

Environment:
Production.

Failure Threshold:
Availability drops below 99.0% in any 1-hour window.

Monitoring Method:
Health check probes, synthetic transaction monitoring.

Test Method:
Chaos testing, failover testing, dependency outage simulation.

Priority:
High.
```

### Reliability

```text
NFR-RELI-01

Metric:
Experiment execution completion rate.

Measurement Method:
Experiments that reach terminal state (success, failure, or cancelled) divided by experiments initiated.

Target:
>= 99.9% of initiated experiments reach terminal state.

Environment:
Production.

Failure Threshold:
Completion rate drops below 99.0% in any 24-hour window.

Monitoring Method:
Job queue monitoring, dead letter queue alerting.

Test Method:
Chaos testing, worker failure injection, queue failure simulation.

Priority:
High.
```

### Durability

```text
NFR-DURAB-01

Metric:
Evidence and trace data durability.

Measurement Method:
Percentage of evidence records surviving a simulated storage failure.

Target:
>= 99.999% data durability (five nines).

Environment:
Production with object storage replication enabled.

Failure Threshold:
Any confirmed data loss event.

Monitoring Method:
Periodic integrity verification, checksum validation.

Test Method:
Storage failure simulation, backup restoration test.

Priority:
High.
```

### Security

```text
NFR-SEC-01

Metric:
Tenant data isolation.

Measurement Method:
Cross-tenant data access attempts via automated penetration test.

Target:
Zero cross-tenant data leakage.

Environment:
Production-equivalent staging with multiple test tenants.

Failure Threshold:
Any confirmed cross-tenant data access.

Monitoring Method:
Authorization audit logging, tenant boundary violation detection.

Test Method:
Automated penetration test suite, manual red-team exercise.

Priority:
Critical.
```

```text
NFR-SEC-02

Metric:
Secret and credential exposure in traces and evaluation records.

Measurement Method:
Automated scan of stored traces and results for patterns matching API keys, tokens, and credentials.

Target:
Zero unredacted secrets in stored data.

Environment:
All environments.

Failure Threshold:
Any confirmed secret exposure in stored data.

Monitoring Method:
Continuous secret detection scanning.

Test Method:
Automated scan test, manual verification with seeded test data.

Priority:
Critical.
```

```text
NFR-SEC-03

Metric:
PII redaction completeness.

Measurement Method:
Automated scan of traces and results for PII patterns (SSN, email, phone, address) that should be redacted.

Target:
>= 99.9% PII redaction rate for classified PII types.

Environment:
All environments.

Failure Threshold:
Redaction rate drops below 99.0%.

Monitoring Method:
Continuous PII detection scanning on stored data.

Test Method:
Automated scan test with seeded PII test cases.

Priority:
High.
```

### Safety (Non-Compensatory Policy)

```text
NFR-SAFE-01

Metric:
Critical safety metric blocking enforcement.

Measurement Method:
Experiments with critical safety failures that were deployed despite blocking policy.

Target:
Zero deployments bypassing critical safety blocking.

Environment:
Production and staging.

Failure Threshold:
Any deployment bypassing a critical safety gate.

Monitoring Method:
Gate enforcement audit log, deployment pipeline monitoring.

Test Method:
Policy enforcement test suite with seeded safety failures.

Priority:
Critical.
```

### Observability Coverage

```text
NFR-OBS-01

Metric:
Trace coverage of AI system components.

Measurement Method:
Percentage of target components (LLM calls, retrieval, tool calls, memory operations) emitting traces.

Target:
>= 95% component coverage for instrumented targets.

Environment:
Production.

Failure Threshold:
Coverage drops below 90% for any component type.

Monitoring Method:
Component trace emission monitoring.

Test Method:
Instrumentation verification test suite.

Priority:
Medium.
```

### Cost Control

```text
NFR-COST-01

Metric:
Evaluation cost per experiment.

Measurement Method:
Sum of target invocation cost and evaluator cost per experiment run.

Target:
P95 evaluation cost does not exceed 150% of baseline cost for equivalent experiment configuration.

Environment:
Production.

Failure Threshold:
P95 cost exceeds 200% of baseline for 3 consecutive experiment runs.

Monitoring Method:
Cost tracking dashboard with per-experiment cost alerting.

Test Method:
Cost regression test suite, manual cost review.

Priority:
Medium.
```

### Data Retention

```text
NFR-RETAIN-01

Metric:
Configurable data retention enforcement.

Measurement Method:
Percentage of data categories with retention policies configured and enforced.

Target:
100% of data categories have retention policies; 0% of expired data remains past retention window.

Environment:
Production.

Failure Threshold:
Any data category without a retention policy, or expired data retained beyond window.

Monitoring Method:
Retention policy audit, automated expired data scanning.

Test Method:
Retention enforcement test with seeded expired data.

Priority:
Medium.
```

### Reproducibility (Version Everything)

```text
NFR-REPRO-01

Metric:
Experiment reproducibility.

Measurement Method:
Re-execution of identical experiment configuration (same dataset version, target version, evaluator version, evaluator prompts) produces results within stochastic tolerance.

Target:
>= 95% of re-executed experiments produce results within 5% of original scores (where stochastic variance is expected).

Environment:
Staging with identical configuration.

Failure Threshold:
Reproducibility rate drops below 90%.

Monitoring Method:
Periodic reproducibility verification runs.

Test Method:
Reproducibility test suite with controlled re-execution.

Priority:
High.
```
