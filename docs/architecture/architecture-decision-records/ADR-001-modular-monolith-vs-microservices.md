# ADR-001: Modular Monolith over Premature Microservices - Status: Accepted

## Status

Accepted

## Date

2026-08-30

## Context

AEGIS is a modular monolith control plane for evaluating, testing, observing, securing,
and verifying AI systems. Its domain spans Identity, Projects, Targets, Datasets,
Experiments, Execution, Tracing, Evaluation, Analysis, Regression, and Reporting. Each
of these is a bounded area with real complexity.

The design interrogation in `grilling.md` is unambiguous on the risk of getting the
topology wrong:

- Q19: "What is the biggest architecture mistake?" — **Premature microservices.**
- README §4: "Do not create 50 microservices. Start as a **modular monolith**."

Operating a distributed system of many independently deployed services adds operational
overhead, deployment complexity, network failure modes, and data-consistency burden
before there is any evidence that independence is needed. For a platform whose value is
trustworthy, reproducible measurement, premature distribution undermines that goal: it
multiplies the moving parts that can silently corrupt or lose evidence.

The system must still separate authority from execution from verification. The
Control, Execution, and Evidence planes are separated conceptually and in code modules,
but they are not independently deployed services at the outset.

## Decision

AEGIS starts as a **modular monolith**: a single deployable application whose domain
modules are strictly boundary-separated in code (the Control, Execution, and Evidence
planes), sharing one operational process and one transactional database.

Execution workers are the one exception to "single process" and it is deliberate: they
are packaged as a separately deployable and runnable worker process from day one,
because AI targets can crash, time out, loop, and consume unbounded resources. This is
an **isolation** decision driven by the untrusted-execution requirement (grilling.md
Q68-Q70), not a microservices decision. Workers remain part of the same codebase and
the same architectural module.

## Consequences

### Positive

- **Simple operations.** One deployable, one upgrade path, one process to reason about
  for most of the system. This is the dominant MVP requirement (README §16 explicitly
  rules out Kubernetes, Kafka, microservices, and a service mesh as "architecture
  theater" for the MVP).
- **Simple database schema evolution.** Relational state lives in one PostgreSQL schema;
  cross-module referential integrity is enforceable with foreign keys and transactions.
- **Fast, coherent iteration.** Module boundaries are expressed in code and enforced by
  layer rules, so teams move quickly without network boundaries getting in the way.
- **No premature cost.** No service-discovery, network-partition, or distributed-
  transaction overhead that has not been justified.
- **Isolation where it is genuinely required.** Untrusted target execution is still
  isolated in separate worker processes, preserving the security boundary that matters.

### Negative

- **Shared failure domain.** A fault in one module can take down the shared process.
  Mitigation: strict module boundaries, enforcement of layer dependency direction, and
  isolated worker processes for untrusted execution so that a crashing target does not
  take down the control plane.
- **Scaling limits.** Independent horizontal scaling of a single module is constrained;
  the whole monolith scales as one unit.
- **Autonomy and deployment-cadence limits.** Separate teams cannot ship modules on
  independent schedules without coordinating, which can slow large-team velocity later.

## Alternatives Rejected

- **Full microservices** — the largest architecture mistake per grilling.md Q19;
  unacceptable operational overhead with no evidence of need.
- **Serverless functions** — cold starts hurt bursty evaluation jobs and orchestration
  across long-running target interactions becomes complex.
- **A single flat module with no boundaries** — would violate the authority-versus-
  execution-versus-verification separation that the whole platform depends on.

## When to Revisit

Revisit when evidence shows a real need for independent scaling, team autonomy, or
deployment cadence: measured, sustained load that one deployable cannot handle while
remaining healthy, or organizational friction that independent shipping would clearly
resolve. At that point the modular boundaries already drawn in code become the seams
for extracting services with minimal rework.

## Linked Documents

- grilling.md Q18, Q19 (architecture mistakes), Q68-Q70 (untrusted execution isolation)
- README.md §2, §4 (top-level and domain architecture; "Do not create 50 microservices")
- README.md §16 (MVP architecture: no Kubernetes / Kafka / microservices / service mesh)
- docs/architecture/high-level-architecture.md
- docs/architecture/development-architecture.md
