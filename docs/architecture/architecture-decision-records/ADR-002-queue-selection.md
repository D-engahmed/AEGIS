# ADR-002: Redis-Backed Job Queue (No Kafka Initially) - Status: Accepted

## Status

Accepted

## Date

2026-08-30

## Context

Evaluation in AEGIS is scheduleable, bursty background work. An experiment can fan out
into thousands of test executions (README §3: 1,000 test cases each running a target
version), each of which needs a job to run reliably: create, schedule, retry, timeout,
cancel, aggregate, and report. The orchestration must survive worker failure, honor
mandatory timeouts, bound retries, and never duplicate side effects.

The design interrogation in `grilling.md` is explicit about the technology choice:

- Q179: "First queue technology?" — **Redis-backed queue is sufficient.**
- Q180: "Kafka immediately?" — **No.**
- Q181: Why — **"Kafka solves durable streaming/event distribution, not every
  background-job problem."**

Project guidance repeats the same idea (README §12): "Don't use Kafka here unless you
have a real reason. Kafka can be added later for high-scale event streams." With no
demonstrated high-throughput event-stream requirement, adopting Kafka now would add
operational weight (brokers, retention management, consumer-group semantics) that the
actual job-scheduling workload does not justify.

## Decision

AEGIS uses a **Redis-backed durable job queue** for evaluation job scheduling, built
with one of Celery, Dramatiq, or ARQ on Redis. Kafka is **not** adopted initially.

The queue is governed by an explicit queue contract that every worker and orchestrator
must satisfy, derived from the execution requirements (FR-EXE):

- **Unique job IDs** — every job has a globally unique identifier (grilling.md Q183).
- **At-least-once delivery with idempotency** — retries are safe and must not duplicate
  side effects (Q195-Q196; FR-EXE-05). Consumers treat job completion as idempotent.
- **Bounded retry with exponential backoff and error classification** — never infinite
  retries, because failed AI calls become cost explosions (Q184-Q188; FR-EXE-02).
- **Timeout** — mandatory per-target, per-test, and overall experiment timeouts
  (Q189-Q192; FR-EXE-03).
- **Cancellation** — cooperative cancellation plus hard timeout (Q194; FR-EXE-04).
- **Dead-letter** — jobs that exhaust their retry budget are routed to a dead-letter
  queue for visibility and alerting rather than silently lost.

## Consequences

### Positive

- **Simple mental model and operations.** A Redis queue is easy to reason about, deploy,
  and monitor. It keeps the MVP minimal in line with README §16.
- **Right fit for the workload.** Evaluation is bursty background job scheduling, which
  is exactly the problem a Redis-backed queue solves well.
- **Modern queue features without Kafka weight.** Bounded retries, backoff, timeouts,
  cancellation, and dead-lettering are first-class in Celery / Dramatiq / ARQ.
- **Reusable Redis.** Redis is already used for caching, distributed locks, and rate
  limits (ADR-003), so one operational dependency serves multiple needs.

### Negative

- **Surviving large failure domains.** A Redis-backed queue does not provide the same
  long-term durability and replay guarantees as a log-based system; surviving a major
  failure and reprocessing from a committed log is harder.
- **Limited long-term event streaming.** High-throughput event streams, long retention
  of event history, and multiple independent consumers with their own replay cursors are
  not a natural fit and would strain the queue.
- **Single-authority queue.** A Redis-fanout model fits the current one-orchestrator
  shape but becomes awkward as the number of independent consumers grows.

## Alternatives Rejected

- **Kafka immediately** — solves durable event distribution, not the background-job
  problem; adds brokers and retention complexity before any high-scale event-stream
  need exists (grilling.md Q180-Q181).
- **A bespoke in-memory scheduler** — loses durability, retry, and dead-letter
  guarantees needed for reliable evidence production.

## When to Revisit

Revisit when there is evidence of high-throughput event streams, a requirement for long
retention and replay of event history, or several independent consumers that each need
their own durable cursor. At that point Kafka (or a compatible stream platform) can be
introduced alongside or in place of the job queue for the streaming path only, without
changing how discrete evaluation jobs are scheduled.

## Linked Documents

- grilling.md Q179-Q183 (queue technology), Q184-Q198 (retry, timeout, cancellation,
  idempotency)
- README.md §3 (thousands of test executions), §12 (orchestration, Redis + worker pool)
- docs/requirements/functional-requirements.md FR-EXE-01 .. FR-EXE-07
- docs/architecture/execution-architecture.md
