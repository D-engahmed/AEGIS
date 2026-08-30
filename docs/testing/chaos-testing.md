# Chaos Testing

## Purpose

Chaos testing is deliberately destructive. AEGIS is a reliability and verification control plane, so its own failure behavior is a first-class product property. Chaos testing proves the failure architecture (`docs/architecture/failure-architecture.md`) holds when the world misbehaves: when infrastructure dies, when providers go dark, when the network drops, and when the queue redelivers work to a system that was mid-flight. If AEGIS cannot prove its own reliability under attack, its reliability verdicts for other AI systems are worthless.

The governing failure-architecture principles are restated here because chaos testing exists to prove them:

```text
Fail contained, retry deliberately, never silently duplicate side effects.
Predictable failure under unpredictable conditions.
No score without evidence.
```

## What We Deliberately Kill

```text
Worker
Redis
Database Connection
Evaluator Process
Target Provider
Network
Object Storage
```

- **Worker**: terminate a worker mid-job while the job is still inflight, then redeliver.
- **Redis**: kill the queue and cache during active execution; restart and observe recovery.
- **Database connection**: sever the application and worker database connections during writes.
- **Evaluator process**: kill an evaluator plugin process while it is scoring, mid-RPC.
- **Target provider**: black out the target provider (timeouts, 500s, malformed responses, rate limits) at scale.
- **Network**: partition, delay, and drop packets between control plane, workers, and dependencies.
- **Object storage**: make artifact and evidence uploads fail mid-write.

## And Ask

```text
Did execution duplicate?
Did evidence corrupt?
Did retry storm happen?
Was the user notified?
Did the system recover?
```

Each kill maps to an invariant. A chaos run is not a demonstration that something breaks; it asks a specific question and records a specific answer.

## Chaos Gamut

| Failure Injection | Expected System Behavior | Invariants That Must Hold |
|---|---|---|
| Worker killed mid-job, job redelivered | Idempotent reprocessing; execution ID and idempotency key prevent duplication | Bounded retries; no duplicated side effects; no duplicate records |
| Redis / queue failure | Fail-closed or degrade per policy; jobs not silently dropped; queue recovery resumes processing | Bounded retries; no loss without audited drop; partial evidence preserved |
| Database connection severed mid-write | Transaction rollback; failed executions classified; connection pool recovers | Partial evidence preserved; failed never mislabeled as cancelled |
| Evaluator process killed mid-RPC | The execution reports evaluator failure; scoring is not half-recorded; no control-plane crash | Failed != cancelled; no evidence corruption; no uncollected scores masquerading as results |
| Target provider blackout at scale | Rate-limited, malformed, and timeout responses classified; bounded backoff with jitter; no retry storm | Bounded retries; no retry storm; no duplicated side effects; user notified |
| Network partition / delay / packet loss | Requests eventually classified as failed or degraded; no hang; no duplicate submits | Bounded retries; predictable failure; no silent duplication |
| Object storage unavailable | Uploads fail with clear classification; partial artifacts never treated as complete; reports not finalized from incomplete artifacts | Partial evidence preserved; failed != cancelled; no corruption |

### Invariant Details

- **Bounded retries**: no retryable failure ever retries more than the configured maximum. Chaos runs verify the counter is honored under real failure, not only in unit logic.
- **No duplicated side effects**: redelivered or retried work does not create a second execution, a second set of records, or a repeated external effect. Idempotency keys are proven under actual redelivery.
- **Partial evidence preserved**: when a run fails partway, the completed portion of evidence is durable. A chaos failure never silently drops evidence; "no score without evidence" holds on failure paths.
- **Failed != cancelled**: a failed execution records its failure class; a cancelled execution records cancellation by an identity. Chaos-created failures are never indistinguishable from user cancellations.
- **No retry storm**: backoff with jitter spreads synchronized retries; a provider blackout does not amplify load into a storm.

## Controlled Environment

Chaos runs execute in staging, never production and never a shared developer environment. Staging must model production topology closely enough that a chaos failure is meaningful — same component processes, same queue, same storage layout — but is safe to damage. Chaos workloads use synthetic tenants and seeded data; a chaos run must never damage evidence that a real evaluation depends on.

Access to chaos execution is restricted to operators who are authorized to run destructive tests. Chaos runs are scoped to their synthetic tenants and cleaned up after the chart is verified.

## How Chaos Feeds Failure Architecture and Incident Response

Chaos testing is not a one-off demo. Each run feeds the documented failure architecture and the incident-response procedure:

- **Failure architecture**: a chaos run that exposes a violated invariant is a finding against `docs/architecture/failure-architecture.md` — the architecture must be fixed or the invariant clarified. The chaos gamut is the operational proof of the failure taxonomy, retry policy, and execution state machine.
- **Incident response**: chaos findings generate the runbook conditions for `docs/operations/incident-response.md`: operators practice restoring infrastructure, verifying evidence integrity, and containing spread in a controlled setting rather than during a real incident.
- **Monitoring and alerting**: chaos runs verify that the alerts operators rely on actually fire: notification on failed or cancelled executions, security-incident escalation, and evidence-integrity alarms.

## Schedule

Chaos runs are destructive and expensive. They are tagged `expensive` and `safety`, and run on a fixed schedule defined in the CI/CD gates (for example, per release and on a regular cadence), not on every commit. Each run targets a subset of the gamut, records the injections, the observed behavior, and the invariant verdicts, and archives the report as an artifact.