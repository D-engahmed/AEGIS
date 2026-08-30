# Data Ownership

This document defines who owns which data in AEGIS: how tenant ownership is expressed, what data classification means for storage and access, which pipeline components may read or write each store, and why AEGIS itself must be treated as a sensitive system. It complements `docs/architecture/security-architecture.md` and `docs/architecture/write-architecture.md`.

## Tenant Ownership

Every tenant-owned persistent record carries both `organization_id` and `project_id` (grilling.md Q80-Q81). The **Organization** is the top-level tenant; the **Project** is the unit beneath it (a team's AI application). Ownership is not decorative: it is the primary boundary that separates one customer's data from another's.

### Isolation Is Enforced at Every Boundary, Not Application Code Alone

Tenant isolation cannot rely on application code alone (grilling.md Q82-Q85). AEGIS enforces it at each of these boundaries:

- **API.** Authorization checks are organization-scoped and project-scoped before any domain logic executes. Permissions are first-class; roles bundle permissions (`write-architecture.md`).
- **Storage.** Every tenant-scoped query and index is prefixed with `(organization_id, project_id)` so reads are naturally restricted to the caller's tenant (`database-design.md`).
- **Telemetry.** Trace and telemetry ingestion tags ownership, and the trace store applies the same tenant scoping. Evaluation evidence is never an anonymous blob.
- **External integrations.** Exports, reports, webhooks, and CI/CD integrations are authorized as their owning organization/project and never leak across tenants.

### PostgreSQL RLS as Defense in Depth

PostgreSQL **Row-Level Security (RLS)** is a strong candidate as a defense-in-depth control for tenant isolation, especially for SaaS (grilling.md Q83; ADR-003). RLS is not a substitute for the boundaries above; it is an additional guarantee that even a misbehaving query path cannot read across tenants. It is planned as a second layer, not the only layer.

## Data Classification Levels

Every data object carries a classification that governs how it is stored, who may access it, and how it is retained. Classifications are configurable per organization and per record type, but these five levels are the default vocabulary (grilling.md Q96-Q97):

| Level | Implies for storage | Implies for access | Implies for retention |
|---|---|---|---|
| **Public** | May be stored without additional controls. | Accessible to anyone with system access; no special authorization. | Standard retention; can be freely retained or pruned. |
| **Internal** | Standard storage; no special encryption beyond baseline. | Accessible to authenticated member of the owning organization (default viewer). | Standard configurable retention. |
| **Confidential** | Storage with records-level access controls; sensitive fields may be redacted before storage. | Restricted to authorized roles (Engineer/Owner/Admin by default). Viewing raw payloads may require explicit authorization. | Shorter default retention; deletion is audited. |
| **Restricted** | Strong controls: access-limited storage, redaction of PII/secrets before persistence, restricted export. | Limited to explicitly authorized principals; role-gated; red-team and attack payloads typically fall here. | Tighter retention with explicit renewal; deletion is audited and approval-gated. |
| **Regulated** | Additional legal/regulatory controls (data residency, compliance holds, and legal/datalac retention) beyond technical controls. | Strict role gating; often requires approval and audit trail per access. | Subject to legal hold and compliance retention; deletion is controlled and documented. |

## Data Type to Classification and Access Mapping

Traces are the primary concern: they can contain prompts, retrieved documents, PII, agent reasoning, and secrets (grilling.md Q93-Q94, Q458-Q461). The table below maps the main data types to a default classification and who may view them.

| Data type | Default classification | Who may access / view |
|---|---|---|
| **Traces** | Confidential to Restricted | Traces may contain PII and secrets; **redaction is applied before storage** (PII redaction plus secret detection; accidental secrets are treated as a security incident). Authorization to view **raw** traces is granted only to explicitly authorized roles, not the default viewer. Aggregated or redacted views may be available more broadly. |
| **Prompts** | Confidential | Prompts are evaluator/test configuration and application IP. Access limited to authorized project members; raw prompt content is not exposed by default. |
| **Outputs** | Confidential | Model outputs may contain PII or secrets; redacted views for general access, raw output restricted to authorized roles. |
| **Datasets** | Internal to Restricted | Project members who can run evaluations may read datasets; test sets may be hidden from developers for high-stakes benchmarks (grilling.md Q134); adversarial/red-team datasets are Restricted. |
| **Reports** | Internal to Confidential | Viewable by project roles per the classification; export is authorization-checked and audited. |
| **Audit logs** | Restricted | Viewable only by Owner/Admin and auditors; never exposed to general viewers; append-only (`data-lifecycle.md`). |
| **API keys / credentials** | Regulated / Restricted | Never stored in plaintext; hashed at rest; only service that authenticates may read; never part of evaluation records or target metadata (grilling.md Q60). |

The guiding principle: **by default, users should not see raw trace content.** Only authorized roles may view it, and even then redaction happens before storage so the full fidelity is the exception rather than the default.

## Pipeline Ownership

Ownership also answers *which pipeline component may read and write each store*. No component silently bypasses the ownership or classification rules.

| Store | Writers | Readers / owners |
|---|---|---|
| **PostgreSQL (metadata/results)** | The API and application services (Control and Evidence Plane write paths) within the write transaction; execution workers persist terminal execution and result records through their own transactional writes. | The API/read services, the dashboard, and analysis/regression engines, all under tenant scoping. |
| **Redis (queue/cache/locks/rates)** | The API and orchestrator enqueue jobs; workers and the orchestrator write cache, locks, and rate-limit counters. | The orchestrator and workers consume the queue; the cache is read by request-serving paths. Redis holds recoverable operational state, not authoritative records. |
| **Object storage (artifacts)** | The Evidence Plane writes artifacts (datasets, trace payloads, reports, attack payloads) and records stable references. | The Evidence Plane, analysis, and reporting read artifacts by key; access is classification- and tenant-gated. |
| **Trace store (ADR-005)** | The ingestion/trace collector writes spans following OpenTelemetry-compatible semantics, after redaction. | The Evidence Plane, dashboard, and debugging views read spans; evaluation evidence is never sampled away. |

The authoritative records live in PostgreSQL and object storage. Redis is recoverable state. The trace store holds evidence that must be preserved.

## AEGIS Itself Is a Sensitive System

AEGIS is not a passive database — it is a control plane that owns evaluation datasets, prompts, guardrail policies, and tools capable of evoking or diagnosing sensitive AI behavior (grilling.md Q100). Three consequences follow:

1. **AEGIS data is a target.** Its datasets and traces are an attractive target for adversaries (prompt, tool, model, and guardrail configuration reveal attack surface). Its own storage must be treated as sensitive, with Restricted/Regulated classification applied where appropriate and strong controls on the raw data.
2. **AEGIS holds credentials and authority.** It manages scoped API keys, service accounts for CI/CD, and authorization to call targets. A compromise of AEGIS could authorize destructive tool calls or expose production integration secrets. It must be secured accordingly (`docs/architecture/security-architecture.md`).
3. **AEGIS's own evidence must be trustworthy.** Because its output gates deployments, the integrity and immutability of its results are a security property, not just a data-quality nicety. If an attacker can alter historical results, they can falsify safety verdicts. This is why immutability, audit, and append-only logging (`immutability-rules.md`, `data-lifecycle.md`) are enforced as security controls.

## Related Documentation

- `docs/architecture/security-architecture.md` — the threat model and authorization boundaries.
- `docs/data/database-design.md` — how ownership columns and tenant-scoped indexes realize this in the schema.
- `docs/data/retention-and-deletion.md` — how classification drives retention and deletion controls.
- `docs/data/data-lifecycle.md` — when and how data transitions and who performs the transitions.
- `docs/architecture/architecture-decision-records/ADR-003` — RLS as a tenant-isolation candidate.
