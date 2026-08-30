# Stress Testing

## Purpose

Stress testing proves AEGIS behavior at and beyond designed limits. The agent does not write "the system is scalable" unless a stress benchmark says so. Stress testing is the evidence behind such claims: it establishes the load at which the system degrades, what it does when it degrades, and that it fails contained rather than corrupting.

Stress testing is distinct from load testing. Load testing verifies the system behaves correctly under normal and anticipated-peak load. Stress testing pushes past that to find the breaking point and prove the system fails predictably there.

## What Is Stress Tested

```text
500 concurrent executions
1000 concurrent API users
Queue backlog
Evaluator bottleneck
Database saturation
Artifact upload pressure
Trace ingestion pressure
```

## Scenarios

Each scenario defines the target numbers, the pass criteria, the tooling and measurement, and the evidence that must be captured. A scenario with no target number is not a test; it is a hope.

### 500 Concurrent Executions

- **Scenario**: 500 experiment or test executions running concurrently across the worker pool.
- **Target numbers**: 500 concurrent executions; the execution-architecture worker model sized accordingly (`docs/architecture/execution-architecture.md`).
- **Pass criteria**: All executions reach a terminal state; no duplicate executions or side effects; evidence preserved per execution; the queue drains after run completion.
- **Tooling and measurement**: Load generator issuing run-creation requests; worker, queue, and database telemetry captured concurrently.
- **Evidence**: Number of executions started and completed, terminal-state distribution, duplicate-execution count, queue depth over time, worker utilization, latency of run completion under the load.

### 1000 Concurrent API Users

- **Scenario**: 1000 concurrent API clients issuing control-plane operations (reads, creates, updates) against the scheduler.
- **Target numbers**: 1000 concurrent users; API latency within the NFR-PERF-01 envelope.
- **Pass criteria**: p50, p95, and p99 latency within budget; error rate within threshold; no tenant cross-contamination under load.
- **Tooling and measurement**: HTTP load generator with realistic mixes of reads and mutating calls; per-user identities that must not leak across tenants.
- **Evidence**: Latency percentiles, error codes, per-endpoint breakdown, tenant-isolation checks under load, resource utilization.

### Queue Backlog

- **Scenario**: The queue is loaded with a backlog far larger than the worker pool can drain immediately.
- **Target numbers**: A backlog of many thousands of jobs against the configured worker count.
- **Pass criteria**: The backlog drains; no jobs lost, duplicated, or silently dropped; bounded retries hold even while the backlog is deep; backpressure surfaces to the control plane.
- **Tooling and measurement**: Job injection at a rate exceeding drain rate; queue-depth monitoring; dead-letter monitoring.
- **Evidence**: Backlog depth over time, drain rate, loss and duplication counts, retry counts, and any throttling decisions with their rationale.

### Evaluator Bottleneck

- **Scenario**: Every execution requires evaluator scoring through the plugin boundary, and evaluators become the slowest stage.
- **Target numbers**: Evaluator throughput at the architecture's concurrency ceiling, including LLM-judge evaluators at scale.
- **Pass criteria**: Evaluator saturation degrades gracefully: backpressure or escalation, no uncollected scores, no evidence loss, no crash of the control plane.
- **Tooling and measurement**: Evaluator isolation boundary telemetry; worker-to-evaluator RPC latency and concurrency.
- **Evidence**: Evaluator throughput, RPC latency, queue of pending evaluations, scaling impact on end-to-end completion, and failure behavior at saturation.

### Database Saturation

- **Scenario**: The database is driven to high connection and query saturation by concurrent reads and writes of runs, metrics, and evidence.
- **Target numbers**: Connection pool at `PostgreSQL` limits; query volume saturating the pool.
- **Pass criteria**: No corrupted or lost records; failure falls to "fail closed or degrade" per policy; the application fails predictably rather than hanging; partial evidence preserved.
- **Tooling and measurement**: Query load generator; connection-pool and slow-query telemetry.
- **Evidence**: Query latency percentiles, connection pool behavior, error behavior under saturation, record integrity after the run.

### Artifact Upload Pressure

- **Scenario**: Large artifacts (trace payloads, datasets, reports) are uploaded to object storage at high concurrency.
- **Target numbers**: Concurrent upload volume consistent with stress-scale runs.
- **Pass criteria**: Uploads either succeed or fail with a clear, retryable classification; no partial artifacts treated as complete; no report finalization from incomplete artifacts.
- **Tooling and measurement**: Object-storage concurrency generator; artifact integrity checks after upload.
- **Evidence**: Upload latency, completion and failure counts, integrity verification results, and cleanup behavior.

### Trace Ingestion Pressure

- **Scenario**: Trace volume far exceeds normal production ingestion while evaluation runs in parallel.
- **Target numbers**: Trace ingestion volume at multiples of the NFR-PERF-02 target.
- **Pass criteria**: Ingestion latency within budget or explicitly degraded with backpressure; zero trace loss without an explicit, audited drop; evaluation results still linkable to traces.
- **Tooling and measurement**: Trace generator; ingestion pipeline latency monitoring.
- **Evidence**: Ingestion rate, p95 ingestion latency, drop counts, linkage integrity between traces and results.

## Scheduling and Artifacts

Stress runs are expensive. They are tagged `expensive` and scheduled on a cadence, not run on every commit. The schedule is configured in the CI/CD gates. Results are archived as artifacts: the load configuration, the measurements, the pass-or-fail verdict per scenario, and the evidence captured. A stress claim in any document must reference an archived stress report; an archived report is the only acceptable source for statements about the system's limits.