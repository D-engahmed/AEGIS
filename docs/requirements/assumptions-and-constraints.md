# Assumptions and Constraints

> Back to [Requirements README](./README.md)

This file captures what we believe to be true (assumptions, which evidence may invalidate) and what we have decided and may only revisit via an Architecture Decision Record (constraints). The traceability of requirements to architecture, code, tests, and CI gates lives in [traceability-matrix.md](./traceability-matrix.md).

---

## Assumptions

Assumptions are things we believe to be true but must verify. Each assumption may be invalidated by evidence, which triggers a review of affected requirements and architecture.

| ID | Statement | Source | Implication |
|---|---|---|---|
| ASM-01 | Evaluation workloads are bursty and asynchronous, not sustained high-throughput streams. | grilling.md Q176-181 | A Redis-backed queue is sufficient initially. Kafka is not needed at launch. |
| ASM-02 | Dataset and target version immutability is essential for historical evaluation meaning. | grilling.md Q45-48 | Old experiments must reference immutable versions. Mutating a dataset or target version after execution invalidates historical results. |
| ASM-03 | Teams will self-host or SaaS-host AEGIS, not embed it inside their AI systems. | grilling.md Q68-70 | AEGIS invokes targets over the network; it does not run inside target processes. Execution isolation is a first-class concern. |
| ASM-04 | LLM judge scores are not ground truth and need calibration. | grilling.md Q226-250 | Every LLM-as-judge metric must store evaluator version, judge model, judge prompt version, and confidence. Human calibration sampling is required for important metrics. |
| ASM-05 | OWASP, DeepEval, Ragas, and OpenTelemetry will be integrated as adapters, not reinvented. | grilling.md Q26-50 | The evaluator architecture must be a plugin system. Threat taxonomies, evaluation metrics, and trace semantics come from external sources. |
| ASM-06 | Aggregate scores hide subgroup failures; slice-level analysis is required. | grilling.md Q143-149 | Every experiment must support dataset slices. Regression detection must operate at the slice level, not only at the aggregate level. |
| ASM-07 | Evaluation should be non-destructive by default; production evaluation must be explicitly authorized. | grilling.md Q72-75 | Tool side effects are disabled or sandboxed unless explicitly configured otherwise. |
| ASM-08 | Some metrics are non-compensatory; a safety failure cannot be overridden by a quality improvement. | grilling.md Q236-248, Q497-498 | Policy gates must support composite logic where safety dimensions are non-compensatory. |
| ASM-09 | Persistent AI state (memory) is part of the attack and reliability surface. | grilling.md Q276-300 | Memory evaluation must cover poisoning, stale memory, cross-tenant leakage, and memory policy enforcement. |
| ASM-10 | Evaluation quality is bounded by test-set quality. | grilling.md Q126-150 | Dataset quality checks (duplicates, near-duplicates, contamination, class imbalance) are mandatory, not optional. |
| ASM-11 | An evaluator is itself a versioned AI dependency. | grilling.md Q222-250 | Evaluator version changes, judge model changes, and judge prompt changes must create new evaluator versions and invalidate cached evaluations. |
| ASM-12 | Every result must be explainable by its configuration. | grilling.md Q151-175 | The evidence graph must link every score to its full configuration chain: dataset version, target version, evaluator version, and execution context. |

---

## Constraints

Constraints are decisions we may not revisit without an Architecture Decision Record. They are frozen until a new ADR explicitly revises them.

| ID | Statement | Source | Implication |
|---|---|---|---|
| CON-01 | Begin as a modular monolith, not microservices. | ADR-001, grilling.md Q19 | All domain modules (projects, targets, datasets, experiments, execution, tracing, evaluation, analysis, policy) run in a single deployable. Inter-module communication is in-process function calls, not network calls. Premature microservices is explicitly rejected. |
| CON-02 | Redis-backed queue initially, not Kafka. | ADR-002, grilling.md Q179-181 | Celery, Dramatiq, or ARQ with Redis as the broker. Kafka may be introduced later for high-scale event streaming, but the initial execution queue is Redis-backed. |
| CON-03 | PostgreSQL for metadata, Redis for queue/cache/locks, object storage for large artifacts. | ADR-003, grilling.md Q734-778 | PostgreSQL stores users, projects, targets, experiments, runs, metrics, results. Redis stores queue state, cache, distributed locks, rate limits. Object storage stores large datasets, trace payloads, reports, and artifacts. |
| CON-04 | Evaluators execute as isolated plugins via an RPC-evaluator interface. | ADR-004, grilling.md Q36-50 | The evaluation engine does not hardcode metrics. Every evaluator is a plugin invoked through a defined interface. Evaluators may be deterministic, semantic, or LLM-as-judge. |
| CON-05 | Traces are stored in a dedicated trace store with OpenTelemetry-compatible semantics. | ADR-005, grilling.md Q451-475 | Aegis does not invent its own trace format. Trace collection follows OpenTelemetry-compatible semantics where practical. AI-specific semantic attributes are added on top. |
| CON-06 | FastAPI is the API framework. | grilling.md Q663 | All REST API endpoints are implemented in FastAPI. |
| CON-07 | Python is the primary implementation language. | grilling.md Q863 | The control plane, execution plane, and evidence plane are implemented in Python. |
| CON-08 | AEGIS does not execute arbitrary customer code inside the control plane. | grilling.md Q68-70 | Target execution happens in isolated workers or customer-controlled runners. Untrusted execution is a major isolation problem that is addressed at the infrastructure level. |
| CON-09 | Production evaluation is not the default. | grilling.md Q72-75 | Tests can mutate data, trigger actions, incur costs, or expose sensitive information. Production evaluation requires explicit authorization. |
| CON-10 | Role-based access control begins with Owner, Admin, Engineer, Analyst, Viewer. | grilling.md Q87 | Permissions are first-class; roles bundle permissions. Service accounts exist for CI/CD and automated evaluation. API keys are scoped to organization, project, environment, or target. |
