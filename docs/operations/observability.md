# Observability

## The Observability Posture

AEGIS observes two things, and both are first-class (`docs/development/layers/10-observability-layer.md`):

1. **AEGIS evaluating other systems**: evaluation traces, evaluator performance, and cost of the AI systems under evaluation.
2. **AEGIS itself**: worker latency, queue depth, evaluator failures, API latency, database health, and trace ingestion.

The governing principle (Q475): **AI telemetry must preserve enough semantic context to explain behavior without becoming a privacy liability.** Telemetry is privacy-treated: PII is redacted before storage and secrets are detected, redacted, and alerted (FR-TRC-04, FR-TRC-05, NFR-SEC-02).

Two sampling rules are non-negotiable:

- **Evaluation traces are evidence and are NOT sampled away** (Q474; FR-OBS-03; ADR-005). Every score is backed by its evidence; sampled-away evidence would break "no score without evidence."
- **Production observability MAY sample** (FR-OBS-02). Production telemetry that is not evidence (traffic, health, non-evaluation spans) is a legitimate sampling candidate to control cost and volume.

## Monitored Signals

The platform monitors the following signals, per the observability layer:

```text
Worker latency
Queue depth
Evaluator failures
Cost
API latency
Database health
Trace ingestion
```

Operators additionally track retry counts, gate verdicts, and error rates by error code, because the failure classes (retryable / non-retryable / deterministic) and the gate outcomes are directly observable.

## SLO-able Signals and the Metric Catalog

Each signal is measured with a defined threshold. Where an NFR defines the target, the threshold is the NFR's. Where it does not, the threshold is an operational severity threshold whose alert classification is defined in `incident-response.md`. Thresholds marked "baseline" are measured per release and configurable via the release gate.

| Signal | What is measured | Threshold / target | Reference |
|---|---|---|---|
| API latency | HTTP request timing, p95, excluding async experiment execution | p95 < 500ms; failure if p95 exceeds 500ms for 5 consecutive minutes | NFR-PERF-01 |
| Worker latency | Time from job claim to terminal state per job; per-test invocation latency | Baseline per release; alert on sustained deviation > 2x baseline, or on timeouts at the per-test boundary | FR-EXE-03 |
| Queue depth | Pending jobs across queues; dead-letter depth | Depth growing beyond sustained work throughput for more than a defined window; dead-letter depth > 0 is pageable | ADR-002, NFR-RELI-01 |
| Evaluator failures | Count and rate of evaluator process/plugin failures, classified | Failure rate beyond baseline; any classification that marks failed != cancelled violations | `failure-architecture.md` |
| Evaluation cost | Target cost and evaluator cost tracked separately, per experiment | p95 cost <= 150% of baseline; failure if p95 exceeds 200% of baseline for 3 consecutive runs | NFR-COST-01 |
| Trace ingestion | Rate, p95 ingestion latency, dropped payloads | p95 < 200ms for payloads under 1MB; failure if p95 exceeds 200ms for 5 consecutive minutes; zero unredacted-secret ingress (any occurrence is a page) | NFR-PERF-02, NFR-SEC-02 |
| Database health | Connection pool usage, active/blocked connections, replication lag, slow queries | Pool saturation > 80% sustained; replication lag beyond the RPO-safe window; slow-query rate beyond baseline | ADR-003 |
| Retry counts | Retries per failure class, out-of-bounds retries | Any retry exceeding the maximum configured count is a defect page; retry-storm indicators (burst of synchronized retries) page | Q184-Q188 |
| Gate verdicts | Pass / warn / block / human-override distribution; gate-enforcement violations | Zero deployments bypassing a critical safety gate | NFR-SAFE-01 |
| Error rates by code | HTTP and worker error rates classified by error code (timeout, rate limit, validation, ...) | Error-rate spikes beyond baseline per code page; deterministic-failure-class error rates are reported, not retried | Q401-Q425 |
| Execution completion rate | Experiments reaching terminal state / experiments initiated | >= 99.9%; failure if it drops below 99.0% in any 24-hour window | NFR-RELI-01 |
| API availability | Successful HTTP responses / total requests | >= 99.5% per calendar month; failure below 99.0% in any 1-hour window | NFR-AVAIL-01 |
| Trace coverage | % target components emitting traces (LLM, retrieval, tool, memory) | >= 95%; failure below 90% for any component type | NFR-OBS-01 |
| Evidence durability | Percentage of evidence surviving simulated storage failure | >= 99.999%; any confirmed data-loss event pages | NFR-DURAB-01 |

Faithfulness of the measurement matters as much as the number: API latency excludes async experiment execution (NFR-PERF-01), cost separates evaluator cost from target cost (Q170), and provider pricing is versioned so cost estimates are not silently wrong (FR-OBS-04).

## Logging Conventions

- **Structured**: JSON-formatted logs with a fixed schema. No free-form text fields that would hide incident-relevant context.
- **Correlation**: every log line carries a correlation ID. The execution ID is the correlation ID linking execution, trace, and evaluation data (`execution-architecture.md`); correlation IDs must survive async boundaries (layer 10 failure mode: correlation IDs lost across async boundaries).
- **No secrets, no PII**: nothing that would violate NFR-SEC-02 or NFR-SEC-03 enters logs. Redaction is applied before the telemetry path, and logging code never emits raw provider responses.
- **Levels**: error for classified failures, warn for degradation, info for routine state transitions. Diagnostic verbosity is an operational knob, not a default.

## Metrics and Traces: OpenTelemetry-Compatible Export

Traces and metrics are exported through OpenTelemetry-compatible exporters (FR-OBS-01; `10-observability-layer.md`), which interoperate with Grafana, Datadog, and other OTel-compatible backends. Exporter failures must **degrade gracefully** — a failed export never blocks the request or worker path (layer 10 failure mode). Export configuration is part of the observability exporters config group (`configuration.md`).

Metric naming is consistent across layers to avoid the layer-10 failure mode of inconsistent naming. Evaluation traces link to evaluation results (FR-TRC-07); traces link to incidents where applicable.

## Dashboards to Build

| Dashboard | Contents |
|---|---|
| **API** | Request rate, p50/p95/p99 latency, error rate by code (NFR-PERF-01), availability, auth/rate-limit failures |
| **Workers** | Worker latency, jobs per worker, worker health, failed vs cancelled state transitions, resource utilization |
| **Queue** | Queue depth per queue, dead-letter depth, dispatch rate, retry counts, retry-storm indicators |
| **Evaluation** | Evaluation run throughput, evaluator failures by class, per-test / per-target timeouts, trace coverage per component (NFR-OBS-01) |
| **Evidence** | Evidence written vs scores written (no-score-without-evidence enforcement), trace ingestion rate/latency, evidence integrity and durability checks, evidence retention state |
| **Cost** | Target cost vs evaluator cost per experiment, per-provider cost, cost vs baseline (NFR-COST-01), evaluator cost alarms |

Percentile dashboards (p50/p95/p99) are required for latency signals per the NFR measurement notes.

## Alerts and Runbook Linkage

Each alert maps to a runbook in `incident-response.md`. The mapping is explicit so an on-call engineer starts from the classification, not from first principles:

| Alert | Severity | Runbook |
|---|---|---|
| Secret detected in output/trace | Critical | Secret leak |
| Tenant-isolation suspicion (cross-tenant access attempt) | Critical | Tenant-isolation suspicion |
| Evidence-integrity / durability violation | Critical | Evidence corruption |
| Execution duplication detected (duplicate side effect) | Critical | Worker crash / duplication suspicion |
| Queue unavailable / dead-letter fill | Major | Queue unavailable; Retry storm |
| Retry storm indicators | Major | Retry storm |
| Database saturation / replication lag | Major | Database saturation |
| Object storage failure | Major | Object storage failure |
| Evaluator process failures above baseline | Minor | Evaluator process failure |
| Target provider outage at scale | Minor | Target provider outage |
| API latency p95 over 500ms for 5 minutes | Major | Performance / capacity |

Severity classification and lifecycle are in `incident-response.md`.

## Related Documentation

- `docs/development/layers/10-observability-layer.md` — the observability layer contract
- `docs/operations/incident-response.md` — alert-to-runbook mapping and severity model
- `docs/requirements/non-functional-requirements.md` — the NFRs that define the measured targets
- `docs/architecture/architecture-decision-records/ADR-005` — why evaluation traces are never sampled
- `docs/operations/configuration.md` — observability exporter configuration