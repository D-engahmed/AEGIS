# Component Architecture

This document is the C4 component view of AEGIS: the internal building blocks of the Control Plane and the specialization components beyond it. Each component is documented with the component template defined in `docs/architecture/README.md`.

The components map to the development layers defined in `docs/development/layers/` (00 system boundaries, 01 domain, 02 application, 03 interface, 04 infrastructure, 05 execution, 06 evaluation, 07 analysis, 08 policy & gates, 09 evidence, 10 observability, 11 security). The mapping is noted on each component.

## API Layer

- **Responsibility**: The authoritative interface surface; it authenticates callers, authorizes actions, validates requests, and routes to services.
- **Inputs**: HTTP requests from engineers, CI/CD, SDK, and the dashboard.
- **Outputs**: Responses and commands to create/update Projects, Targets, Datasets, Experiments, Evaluators, and Policies.
- **Dependencies**: Application services, domain model, infrastructure (PostgreSQL), authorization.
- **Failure Modes**: Routing and validation errors, authorization misconfiguration, dependency outage causing fail-closed behavior.
- **Scaling Model**: Horizontally scalable, stateless HTTP processes.
- **Security Boundary**: It is the only entry point for external callers; it never exposes raw traces or secrets without authorization.
- **Why This Component Exists**: It provides one controlled, authorized surface instead of direct service access.
- **Why It Is Not Combined With Another Component**: It is the interface; merging it with services would bypass cross-cutting enforcement.
- **Technology Choice**: FastAPI.
- **Alternatives Rejected**: Dedicated API gateway (overkill initially); heavier frameworks.
- **When To Replace Technology**: When streaming or eventing at scale exceeds FastAPI's capabilities.
- **Layer**: 03 interface.

## Project / Target Registry

- **Responsibility**: Owns Projects and Targets, their immutable Target Versions, and their relationships to tenancy.
- **Inputs**: Definitions from the API; integration configuration.
- **Outputs**: Target version references used by datasets, experiments, and adapters.
- **Dependencies**: PostgreSQL, authorization, identity/tenancy.
- **Failure Modes**: Invalid references; version immutability violations; tenancy leakage.
- **Scaling Model**: Scales with the control plane process; version history grows relationally.
- **Security Boundary**: Tenancy is enforced per object; secrets never enter the target record.
- **Why This Component Exists**: Targets and versions are the core abstraction around which evaluation is organized.
- **Why It Is Not Combined With Another Component**: It is the source of version truth and must be separated from experimental orchestration.
- **Technology Choice**: Python service over PostgreSQL.
- **Alternatives Rejected**: Folder-based config (loses tenancy and immutability).
- **When To Replace Technology**: When target registry needs to scale beyond relational metadata.
- **Layer**: 01 domain (with 02 application for orchestration).

## Dataset Service

- **Responsibility**: Owns versioned, immutable evaluation Datasets and Test Cases, including quality checks (duplicates, leakage, contamination, coverage).
- **Inputs**: Dataset and test-case definitions; synthetic/adversarial case generation; quality-check requests.
- **Outputs**: Signed/versioned dataset references for experiments.
- **Dependencies**: PostgreSQL for metadata, object storage for large datasets.
- **Failure Modes**: Dataset contamination, invalid references, immutability violations.
- **Scaling Model**: Scales with control plane; large datasets stream from object storage.
- **Security Boundary**: Datasets may be public or private; access is authorized per project.
- **Why This Component Exists**: Evaluation quality is bounded by test-set quality.
- **Why It Is Not Combined With Another Component**: It is separated so immutable dataset versions outlive experiments.
- **Technology Choice**: Python service over PostgreSQL + object storage.
- **Alternatives Rejected**: Inline datasets in experiments (breaks immutability and sharing).
- **When To Replace Technology**: When dataset versioning needs dedicated content-addressed storage.
- **Layer**: 01 domain / 02 application.

## Experiment Service

- **Responsibility**: Owns immutable, reproducible Experiments and publishes work to the execution plane.
- **Inputs**: Experiment definitions referencing targets, datasets, evaluators, and policies.
- **Outputs**: Work items on the queue; experiment state; references to executions.
- **Dependencies**: Target registry, dataset service, evaluator registry, queue, PostgreSQL.
- **Failure Modes**: Invalid or stale references; queue failure blocking dispatch.
- **Scaling Model**: Scales with control plane; work fans out through the queue.
- **Security Boundary**: It only references versions the caller is authorized to use and cannot mutate evidence.
- **Why This Component Exists**: Experiments are the core reproducible evaluation unit.
- **Why It Is Not Combined With Another Component**: It is separated from execution so intent stays reproducible and isolated from untrusted targets.
- **Technology Choice**: Python service over PostgreSQL.
- **Alternatives Rejected**: Running experiments synchronously in the API for all workloads.
- **When To Replace Technology**: When scheduling needs durable multi-node orchestration.
- **Layer**: 02 application.

## Policy Service

- **Responsibility**: Owns Policies/Gates — blocking and advisory rules, non-compensatory logic, and human-override handling.
- **Inputs**: Policy definitions; evidence-graph results and verdicts.
- **Outputs**: Gate outcomes (pass, warn, block, human override) for deployments and releases.
- **Dependencies**: Evidence graph, results, authorization.
- **Failure Modes**: Misconfigured thresholds; flaky metrics causing gate instability; non-compensatory logic misapplied.
- **Scaling Model**: Scales with the control plane; operates over computed evidence.
- **Security Boundary**: Only authorities define/modify policies; execution workers cannot modify policy definitions.
- **Why This Component Exists**: Deployment decisions must be deterministic, evidenced, and non-compensatory.
- **Why It Is Not Combined With Another Component**: To trust its inputs, it is separated from the components that produce them.
- **Technology Choice**: Python service over PostgreSQL.
- **Alternatives Rejected**: Hardcoded gates in CI.
- **When To Replace Technology**: When a dedicated rule engine is justified.
- **Layer**: 08 policy & gates.

## Evaluation Fabric

The evaluation fabric is a plugin architecture of evaluators, each an independent plugin implementing a common `evaluate(execution, context) -> MetricResult` contract. All evaluators preserve evaluator identity, version, judge model, prompt version, and confidence. Each publishes results into the Evidence Plane.

**Shared responsibility**: compute metric results and evidence from executions and traces. **Inputs**: executions, traces, evaluator configuration. **Outputs**: metric results and evidence. **Dependencies**: workers, trace store, results, optional LLM providers. **Failure Modes**: flaky metrics, judge bias, cost explosion on retry. **Scaling Model**: scales with evaluation workers; prompts are versioned. **Security Boundary**: evaluators cannot access the Control Plane; LLM-judge calls are authorized and never return hidden chain-of-thought. **Why This Component Exists**: metrics must be pluggable, versioned, and reproducible, never hardcoded. **Why It Is Not Combined With Another Component**: to keep metrics testable and replaceable independently of execution. **Technology Choice**: plugin registry over trace input. **Alternatives Rejected**: hardcoded metric set. **When To Replace Technology**: when new scopes require a new evaluator SDK. **Layer**: 06 evaluation.

Evaluator plugins (each also a plugin in layer 06):

- **Deterministic evaluators** — schema validity, exact matches, tool names, argument schemas, latency, token counts, cost, mechanically detectable policy violations.
- **Semantic / metrics evaluators** — semantic similarity and answer relevance via embedding models.
- **LLM judge** — probabilistic quality, helpfulness, reasoning, and instruction-following; treated as a versioned AI dependency with confidence and calibration.
- **RAG evaluator** — retrieval (recall, precision, ranking, coverage), evidence (citation correctness, sufficiency, source quality), generation (faithfulness, relevance, correctness), and end-to-end behavior separately.
- **Agent evaluator** — trajectory-level evaluation: goal completion, planning, tools, state, recovery, loops, step efficiency, and budgets.
- **Memory evaluator** — memory reads/writes, wrong recall, staleness, and poisoning.
- **Tool evaluator** — tool selection, arguments, result handling, authorization, hallucination, and ordering.
- **Safety evaluator** — red-team and guardrail evaluation mapped from recognized taxonomies (e.g., OWASP agentic threat model).

## Execution Engine

- **Responsibility**: Job scheduling, worker lifecycle, bounded retries with exponential backoff, mandatory timeouts, cooperative cancellation plus hard timeout, and sandboxing of target/tool/memory execution.
- **Inputs**: Work items from the queue (Redis, not Kafka).
- **Outputs**: Executed target invocations, traces, artifacts, and executions; retry/error classification.
- **Dependencies**: Queue, target adapters, trace store, object storage, sandbox.
- **Failure Modes**: Targets that crash, time out, loop, or consume resources; cost explosion on unbounded retry; duplicate side effects on retry (idempotency).
- **Scaling Model**: Horizontally scalable worker pool, isolated from the Control Plane.
- **Security Boundary**: It executes untrusted targets in sandboxes; it cannot modify policy definitions or decide gates.
- **Why This Component Exists**: Untrusted execution must be contained and scheduled reliably.
- **Why It Is Not Combined With Another Component**: It is isolated from the Control Plane and from policy authority.
- **Technology Choice**: Redis-backed queue (Celery, Dramatiq, or ARQ; not Kafka initially).
- **Alternatives Rejected**: In-process execution; Kafka for initial job queueing.
- **When To Replace Technology**: When durable streaming or dedicated sandbox runtimes are required.
- **Layer**: 05 execution.

## Trace Collector

- **Responsibility**: Ingests OpenTelemetry-compatible traces of model calls, retrieval, tools, memory, guardrails, and agent execution; applies redaction before storage.
- **Inputs**: Traces from workers, target adapters, and SDK/OpenTelemetry ingestion.
- **Outputs**: Trace data to the trace store and downstream to evaluation and the evidence graph.
- **Dependencies**: Object storage, PostgreSQL metadata.
- **Failure Modes**: Privacy leakage if PII/secrets are stored unredacted; storage loss.
- **Scaling Model**: Scales with execution volume; evaluation traces normally unsampled.
- **Security Boundary**: Traces can contain prompts, documents, PII, and secrets; redaction and authorization are mandatory.
- **Why This Component Exists**: Evaluation needs execution context to explain failures.
- **Why It Is Not Combined With Another Component**: It is evidence ingestion, separate from run orchestration.
- **Technology Choice**: OpenTelemetry-compatible semantics.
- **Alternatives Rejected**: A private telemetry format.
- **When To Replace Technology**: When a dedicated tracing backend is justified.
- **Layer**: 04 infrastructure / 09 evidence.

## Analysis Engine

- **Responsibility**: Regression detection, failure classification and clustering, comparison, slicing, and statistical significance over results.
- **Inputs**: Metric results and traces from the evidence graph.
- **Outputs**: Regression signals, failure clusters, comparisons, and significance statements.
- **Dependencies**: Evidence graph, results, statistical utilities.
- **Failure Modes**: Sampling noise misinterpreted as change; flaky metrics producing false regressions.
- **Scaling Model**: Scales with analysis jobs over aggregated evidence.
- **Security Boundary**: It reads evidence under authorization; it does not redefine scores.
- **Why This Component Exists**: Aggregate scores hide subgroup failures; regressions must be detected per test and per slice.
- **Why It Is Not Combined With Another Component**: Analysis must trust immutable evidence and remain neutral to evaluation.
- **Technology Choice**: Python over PostgreSQL aggregates.
- **Alternatives Rejected**: Naive aggregate-only comparison.
- **When To Replace Technology**: When analytical scale demands columnar storage.
- **Layer**: 07 analysis.

## Evidence Graph Service

- **Responsibility**: Maintains the provenance graph linking experiments, versions, executions, traces, artifacts, evaluators, results, and verdicts; enforces "No score without evidence."
- **Inputs**: Results and trace metadata.
- **Outputs**: Provenance, claims, and the basis for analysis and gates.
- **Dependencies**: Results, trace store, artifacts, PostgreSQL.
- **Failure Modes**: Broken links leaving a score without evidence; immutability violations.
- **Scaling Model**: Scales with graph size; relational traversal.
- **Security Boundary**: Append-only and authorized; control actors cannot rewrite evidence.
- **Why This Component Exists**: It implements the central law as a first-class structure.
- **Why It Is Not Combined With Another Component**: It is the proving layer, separate from decision and execution.
- **Technology Choice**: PostgreSQL-backed graph.
- **Alternatives Rejected**: Dedicated graph database initially.
- **When To Replace Technology**: When traversal at scale demands a purpose-built engine.
- **Layer**: 09 evidence.

## Observability

- **Responsibility**: AEGIS's own telemetry — metrics, logs, and traces of the AEGIS system itself — as well as the AI-trace pipeline for targets.
- **Inputs**: Internal instrumentation; target telemetry.
- **Outputs**: Operational telemetry for AEGIS operators; AI traces for evaluation.
- **Dependencies**: Trace infrastructure, metrics/logging backends.
- **Failure Modes**: Telemetry loss, sampling skew, privacy leakage.
- **Scaling Model**: Cross-cutting; scales with system and evaluation volume.
- **Security Boundary**: Cross-cutting visibility; log/telemetry access is authorized.
- **Why This Component Exists**: The system that observes and verifies must itself be observable.
- **Why It Is Not Combined With Another Component**: It is cross-cutting and must not be entangled with any plane's logic.
- **Technology Choice**: OpenTelemetry-compatible.
- **Alternatives Rejected**: Inventing isolated telemetry.
- **When To Replace Technology**: When a dedicated observability backend is justified.
- **Layer**: 10 observability.

## Security / Authz

- **Responsibility**: Authentication, authorization, tenancy, RBAC (permissions first-class, roles bundling permissions), data classification, secret handling, and red-team safety evaluation support.
- **Inputs**: Identity, credentials, and authorization requests; policy definitions.
- **Outputs**: Authorized/denied decisions; scoped credentials; classified-data handling.
- **Dependencies**: Identity infrastructure, PostgreSQL (RLS candidate), logging.
- **Failure Modes**: Authorization bypass, tenant leakage, secret exposure, PII mishandling.
- **Scaling Model**: Cross-cutting; scales with request and tenant volume.
- **Security Boundary**: It is the guard across every plane; no component bypasses it.
- **Why This Component Exists**: Tenancy, classification, and AI-specific risk require coordinated enforcement.
- **Why It Is Not Combined With Another Component**: It is cross-cutting and applies uniformly.
- **Technology Choice**: Application-level authz plus database isolation controls and candidate RLS.
- **Alternatives Rejected**: Relying on application code alone without defense in depth.
- **When To Replace Technology**: When identity/authorization at SaaS scale demands a dedicated provider.
- **Layer**: 11 security.

## Component-to-Layer Mapping

| Component | Layer(s) |
|---|---|
| API Layer | 03 interface |
| Project/Target Registry | 01 domain, 02 application |
| Dataset Service | 01 domain, 02 application |
| Experiment Service | 02 application |
| Policy Service | 08 policy & gates |
| Evaluation Fabric | 06 evaluation |
| Execution Engine | 05 execution |
| Trace Collector | 04 infrastructure, 09 evidence |
| Analysis Engine | 07 analysis |
| Evidence Graph Service | 09 evidence |
| Observability | 10 observability |
| Security/Authz | 11 security |

The system-boundaries layer (00) defines the boundary rules this document and `system-context.md` rely on.
