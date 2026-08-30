# Database Design

This document describes the relational design of AEGIS in PostgreSQL: the transactional metadata and results store from ADR-003. The trace store is a separate, dedicated concern (ADR-005) and is deliberately **not** part of this design. Traces are linked into this model by a stable execution/trace ID (see `docs/architecture/evidence-architecture.md` and `docs/architecture/data-flow.md`).

The design is organized into table groups by concern. For each group this document states its responsibility, its important columns (not full DDL), its immutability notes, and which plane (Control, Execution, or Evidence) owns it.

## Conventions

These conventions apply across every group and are enforced by the application service within the write transaction (`docs/architecture/write-architecture.md`).

- **Tenant ownership.** Every tenant-owned record carries `organization_id` and `project_id`. A record may reference nothing outside its own organization and project. Isolation is enforced at the API, storage, telemetry, and external-integration boundaries, with PostgreSQL RLS as a defense-in-depth candidate (grilling.md Q82-Q84; `data-ownership.md`).
- **Versioning.** Entities whose content can affect an evaluation outcome are versioned. The current draft lives on the base entity; each published/reproducible configuration lives on a version table. Version tables are immutable once published.
- **Evidence linkage.** Results and metric results link to the execution, trace, evidence, and provenance that produced them. The Evidence Graph enforces "No score without evidence" at the write boundary.
- **Write-once results.** Results and metric results are written once and never mutated. There is no update or delete path for these records.
- **IDs.** All primary keys are globally unique, stable identifiers (for example UUIDs), generated before the transaction for executions so duplicate IDs are rejected by a unique constraint and retries cannot duplicate records.
- **Timestamps.** Every record retains `created_at` and, where mutable, `updated_at`. Immutable records carry only `created_at`.

## Identity & Tenancy

Owns: **Control Plane**.

Responsibility: users, organizations, memberships, non-human identities, and the credentials used to authenticate API calls.

| Table | Purpose |
|---|---|
| `organizations` | Top-level tenant. Billing, default classification and retention policy. |
| `users` | Human identities. Auth provider reference, display name, status. |
| `project_members` | Assignment of a user to a project with a set of permissions (roles bundle permissions; permissions are first-class). |
| `service_accounts` | Non-human identities for CI/CD and automated evaluation. |
| `api_keys` | Scoped credentials (organization/project/environment/target where appropriate), hashed at rest, with rotation and revocation metadata. |

Immutability: organizational identity rows are mutable (name, membership) but are never deleted silently; termination is audited. API keys are rotated, never rewritten in place for a released key.

Important columns: `organization.id`, `users.id`, `project_members.project_id` + `user_id` + `permissions`, `api_keys.scope` + `key_hash` + `expires_at`.

## Projects & Targets

Owns: **Control Plane**.

Responsibility: the project boundary and the AI System Target — the central abstraction. Everything under evaluation belongs to a project.

| Table | Purpose |
|---|---|
| `projects` | The unit of tenancy beneath organization. Owns targets, datasets, experiments, evaluators, policies, reports. Carries `organization_id` + `id`. |
| `targets` | A registered AI system (LLM app, RAG pipeline, agent, model API). Identity, type, endpoint, default environment, network policy. |
| `target_versions` | A reproducible snapshot of the target configuration: model, provider, prompt version, tools, retrieval config, memory policy, guardrails, runtime config, and build identity (code commit, image digest). Secrets never enter this record. |

Immutability: `target_versions` are immutable once referenced by an experiment. Changes to a target produce a new version.

Important columns: `target_versions.target_id` + `version_number` + `model` + `provider` + `prompt_version` + `retrieval_config` + `memory_policy` + `guardrail_policy` + `code_commit` + `image_digest` + `config_hash`.

## Datasets

Owns: **Control Plane**.

Responsibility: versioned collections of evaluation scenarios (test cases), including golden/reference information, synthetic, adversarial, and pathological cases.

| Table | Purpose |
|---|---|
| `datasets` | The dataset identity, owner project, labels, slices, classification. |
| `dataset_versions` | An immutable snapshot of a dataset once locked. Tracks the source file/artifact reference in object storage. |
| `test_cases` | One executable/evaluable scenario: input, expected output, expected tool calls, expected retrieval evidence, conversation history, memory/environment state, labels, slice tags. |

Immutability: a `dataset_version` is immutable after it is locked; locking is one-way (`write-architecture.md`). An unlocked draft may be modified freely.

Important columns: `dataset_versions.version_number` + `lock_status` + `artifact_key`; `test_cases.dataset_version_id` + `input` + `expected_output` + `expected_tool_calls` + `labels` + `slices`.

## Experiments

Owns: **Control Plane**; the run it creates belongs to the Execution Plane.

Responsibility: a reproducible evaluation configuration executed against a target version. Reproducibility requires recording every configuration parameter that affects outcome.

| Table | Purpose |
|---|---|
| `experiments` | The experiment configuration: target reference, dataset reference, evaluators, policies, environment, execution settings, seed. |
| `experiment_variants` | A single target/prompt/parameterization arm within an experiment, enabling A/B and multi-target (e.g. GPT vs local) comparisons. |
| `experiment_dataset_links` | The association of an experiment to the versioned dataset it evaluates, capturing the exact locked dataset version. |

Immutability: running and historical experiments (including their variant and dataset links) are immutable snapshots. An experiment can be cloned to create a new variant; the original is not modified.

Important columns: `experiments.configuration` (JSON snapshot of all parameters) + `seed` + `evaluator_set`; `experiment_variants.experiment_id` + `target_version_id` + `parameters`; `experiment_dataset_links.dataset_version_id`.

## Execution

Owns: **Execution Plane** (records are consumed by the Evidence Plane).

Responsibility: the lifecycle of running an experiment: scheduling, worker runs, retries, cancellation, and per-test execution records.

| Table | Purpose |
|---|---|
| `experiment_runs` | A concrete execution of an experiment (a run). Tracks run status and aggregates. |
| `executions` | A single invocation of a target against a test case within a run. This is the Test Execution — the center of the debugging model. Carries input, output, status, cost, latency, and links to the trace. |
| `execution_events` | Structured, time-ordered events emitted during an execution (tool calls, retrieval events, guardrail decisions, errors). Append-like per execution. |

Immutability: an `execution` is write-once after it reaches a terminal state; its record and events are not mutated to change history. Failed/cancelled/partial executions preserve whatever evidence they produced (see `data-lifecycle.md`).

Important columns: `executions.experiment_run_id` + `test_case_id` + `target_version_id` + `input` + `output` + `status` + `cost` + `latency` + `trace_id`; `execution_events.execution_id` + `event_type` + `payload` + `timestamp`.

## Evaluation

Owns: **Evidence Plane**.

Responsibility: the versioned evaluators, their prompt/configuration versions, and the metric definitions they produce.

| Table | Purpose |
|---|---|
| `evaluators` | An evaluator plugin identity and the metadata describing what it measures. |
| `evaluator_versions` | An immutable snapshot of the evaluator: code/plugin version, configuration, judge model, judge prompt version. An evaluator is itself a versioned AI dependency. |
| `metric_definitions` | The definition of a metric: scale, severity (critical/high/medium/low), whether blocking or advisory, flaky tolerance. |

Immutability: `evaluator_versions` are immutable once created; a change produces a new version (so judge-model or prompt changes never invalidate historical comparison).

Important columns: `evaluator_versions.evaluator_id` + `plugin_version` + `judge_model` + `judge_prompt_version` + `configuration`; `metric_definitions.metric_key` + `severity` + `is_blocking` + `flaky` + `scale`.

## Results

Owns: **Evidence Plane**.

Responsibility: the terminal scores, verdicts, and gate conclusions. This is where "No score without evidence" is enforced.

| Table | Purpose |
|---|---|
| `metric_results` | One score for one metric over one execution. Carries evaluator identity/version, judge model, judge prompt version, confidence, score, reason/rationale, and evidence references. |
| `gate_verdicts` | The aggregate or gate conclusion for a run or deployment: pass, warn, block, human override. |

Immutability: `metric_results` and `gate_verdicts` are written once and never mutated. A result cannot exist unless it references experiment, target version, dataset version, evaluator version, execution, and evidence (`write-architecture.md` Result Invariants).

Important columns: `metric_results.execution_id` + `metric_definition_id` + `evaluator_version_id` + `score` + `confidence` + `reason` + `evidence_refs` (trace artifact, dataset case, execution ID); `gate_verdicts.experiment_run_id` + `verdict` + `approvers`.

## Evidence

Owns: **Evidence Plane**.

Responsibility: the lightweight, queryable links and references that make up the Evidence Graph, pointing to object-storage artifacts rather than embedding them.

| Table | Purpose |
|---|---|
| `evidence_links` | Directed links in the evidence graph: execution to trace, result to evidence, verdict to results. |
| `artifact_references` | Stable keys to object storage for traces, datasets, reports, and attack payloads. Stored by key, not content (`evidence-architecture.md`). |

Immutability: evidence links and artifact references are immutable after creation. There is no update path for evidence records.

Important columns: `evidence_links.from_entity` + `to_entity` + `link_type`; `artifact_references.artifact_key` + `class` + `classification` + `retention_expires_at`.

## Reporting

Owns: **Evidence Plane**.

Responsibility: generated evaluation reports, keyed by experiment and report version, with their artifact references.

| Table | Purpose |
|---|---|
| `reports` | The report record: experiment reference, report version, aggregation snapshot, artifact key to the rendered report body in object storage. |

Immutability: a published report is a snapshot; re-generation produces a new report version rather than mutating a released one.

Important columns: `reports.experiment_run_id` + `report_version` + `artifact_key` + `generated_at`.

## Audit

Owns: **Evidence Plane** (system-wide control).

Responsibility: the append-only record of every mutating write.

| Table | Purpose |
|---|---|
| `audit_log` | Identity, action, object, before/after state, timestamp, and approval status for every mutation (`write-architecture.md` Audit Trail). |

Immutability: audit is append-only. Entries are never updated or deleted. Retention follows organization policy and classification.

Important columns: `audit_log.actor_id` + `action` + `object_type` + `object_id` + `before` + `after` + `timestamp` + `approval`.

## Configuration

Owns: **Control Plane**.

Responsibility: versioned policies and guardrail controls that constrain evaluation and deployment.

| Table | Purpose |
|---|---|
| `policies` | A policy identity (e.g. tool-use policy, safety gate policy, retention policy). |
| `policy_versions` | An immutable snapshot of a policy: rules, thresholds, severity. Policy changes produce a new version and may trigger regression tests (grilling.md Q319-Q320). |

Immutability: `policy_versions` are immutable once referenced by an experiment or gate. Changes create a new version.

Important columns: `policies.policy_key` + `policy_type`; `policy_versions.version_number` + `rules` + `thresholds` + `is_enforced`.

## Trace Store (Not in This Design)

Per ADR-005, traces and spans live in the **dedicated trace store**, kept separate from PostgreSQL. This relational design references the trace store only through `executions.trace_id` and the evidence/artifact references. The trace store schema, its OpenTelemetry-compatible semantics, its sampling rules (never for evaluation evidence), and its redaction requirements are documented in `docs/architecture/evidence-architecture.md`, `docs/architecture/data-flow.md`, and ADR-005.

## Indexes & Pagination Strategy

- **Tenant prefix indexes.** Every tenant-scoped lookup uses `(organization_id, project_id, ...)`-prefixed indexes so reads are isolated to a tenant before any other predicate.
- **Execution-centric indexes.** `executions` is indexed by `(experiment_run_id)`, `(test_case_id, target_version_id)`, and `(trace_id)` because execution is the join point for debugging.
- **Results-to-evaluation indexes.** `metric_results` is indexed by `(execution_id)`, `(metric_definition_id, experiment_run_id)`, and `(evaluator_version_id)` to serve regression and per-metric queries.
- **Time-ordered indexes.** Execution events and audit entries are indexed by `(entity_id, timestamp)` for ordered reads.
- **Pagination.** All list endpoints use keyset (cursor) pagination over stable, indexed sort keys (typically `id` or `created_at, id`), never `OFFSET` over large collections. High-volume span data is read from the trace store, not PostgreSQL.

## Related Documentation

- `docs/architecture/write-architecture.md` — Write Invariants that constrain these tables.
- `docs/architecture/evidence-architecture.md` — the Evidence Plane and artifact-reference model.
- `docs/architecture/architecture-decision-records/ADR-003` — the PostgreSQL/Redis/object-storage split.
- `docs/architecture/architecture-decision-records/ADR-005` — the dedicated trace store.
- `docs/data/immutability-rules.md` — which of these tables carry immutable rows and how that is enforced.
- `docs/data/schema-evolution.md` — how these tables may be changed.
