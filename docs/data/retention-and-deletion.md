# Retention and Deletion

This document defines retention policies and deletion rules for AEGIS data. It implements two foundational principles from grilling.md: **retention is configurable** (Q98) and **deletion is auditable** (Q99). It also accounts for storage estimation and cost: retained data has a real footprint and cost, so retention is an active, configurable policy rather than a default to ignore.

Retention is per **data class** and per **organization**, and is overlaid by **data classification** (`data-ownership.md`). A regulated organization may shorten, lengthen, or hold data beyond the defaults here through its own policy. The defaults below are the platform baseline.

## Retention Policies per Data Class

### Traces

Evaluation traces and production traces have **different purposes and different retention**:

- **Evaluation traces are evidence.** They back every score ("No score without evidence"). They must **not** be sampled away or aggressively deleted (grilling.md Q474; ADR-005). They are retained for as long as the experiment, report, gate verdict, or active policy that references them needs them, up to the applicable expiry.
- **Production observability traces** may have a **shorter retention** and may permit sampling, because they are telemetry rather than evidence. Their retention is a configurable operational choice.

Retention of a trace must never outlive the need of an immutable result that references it without that result also being retired.

### Results

Metric results and gate verdicts are immutable. They are retained while referenced by an experiment, report, or baseline, and for a configurable period thereafter to support regression comparison. Because they are immutable, they are not purged opportunistically; their removal is governed by retention expiry and explicit, audited action.

### Artifacts

Object-storage artifacts (trace payloads, dataset files, report bodies, attack payloads) are the large-footprint data. Retention is tied to the referencing entity (dataset version, experiment, report, policy). Attack payloads are Restricted/Regulated and follow the stricter controls below. Artifacts are deleted only when no active reference remains and retention has expired.

### Datasets

Dataset versions are retained while referenced by experiments, reports, or baselines. An archived dataset version may be retained for a configurable period for reproducibility, then deleted-per-policy (datalac: archival may be required instead of hard delete — see below).

### Reports

Published reports are retained for a configurable period for audit and accountability. Re-generating a report creates a new version rather than overwriting a released one, so the retention window applies per report version.

### Audit Logs

Audit logs are **append-only** and retained for a longer, organization-configurable window (frequently the longest window in the system) because they are the record of accountability and legal/regulatory compliance. They are never deleted in routine operation; any removal is governed by the legal/regulated process below.

## Deletion

### Auditable and Role-Gated

Deletion is **auditable** and **role-gated** (grilling.md Q99). Every deletion is recorded in the append-only audit log with identity, action, object, before/after state, timestamp, and approval. Deletions are limited to Owner/Admin roles (and data stewards for Regulated data) — never self-service to general roles (`data-ownership.md`).

### Soft-Delete vs Hard-Delete

- **Soft-delete** marks a record deleted while retaining it for a configurable grace period, allowing recovery and audit. It is used where a mistake could destroy important evidence (datasets, reports, and any record that touches evidence).
- **Hard-delete** physically removes the data (in all stores, including object storage) and is used only after the soft-delete grace period expires, no active references remain, and the audit trail is preserved. Hard-delete never applies to immutable historical data that must be archived.

### Deleting a Project Enforces Referenced-Data Rules

Deleting a project must respect referenced data. A project that owns immutable historical data does **not** simply hard-delete it:

- Active references: block deletion while experiments, reports, gates, or baselines still reference project data.
- Immutable historical data: may require **archival** (detached, tenant-keyed archival) rather than hard delete, so reproducibility and audit survive the project deletion.
- The deletion is a staged, audited workflow: mark for deletion → verify no active references → archive or soft-delete → hard-delete after grace and verification → final audit entry.

This mirrors the "immutable historical data may need archival instead of hard delete" rule: the platform preserves what immutability demands and deletes what policy permits.

### Legal / Regulated (Classified Regulated) Data

Data classified **Regulated** (and Restricted where legal holds apply) is subject to additional controls on top of the defaults:

- **Legal holds** can pause retention expiry — data under a hold is not deleted even past its normal window.
- **Compliance retention and datalac** requirements may require archival and documented preservation rather than hard delete.
- Deletion of Regulated data requires **Owner/Admin plus a data steward/approval**, is audited with full detail, and may require evidence of deletion for compliance.
- Regulated data may carry residency/placement constraints affecting *where* it is stored, not just how long.

## Retention Summary Table

| Data class | Default retention | Min / Max | Owner role (delete) | Exception process |
|---|---|---|---|---|
| Evaluation traces | Retained as long as referencing experiment/report/gate/policy is active, plus configurable grace | Min: as long as references require; Max: org-configurable | Owner/Admin, then Evidence personal data steward for Regulated | Trace removal for privacy/regulatory goes through controlled, audited deletion (`evidence-architecture.md`) |
| Production traces | Shorter, configurable operational window; sampling permitted | Min: short; Max: org-configurable | Owner/Admin | Operators may shorten/lengthen per observability needs |
| Results (metric / verdicts) | Retained while referenced + configurable comparison window | Min: while referenced by a report/baseline; Max: org-configurable | Owner/Admin | Archival instead of delete for immutable historical results |
| Artifacts | Tied to referencing entity (dataset version, experiment, report, policy) | Min: while referenced; Max: org-configurable | Owner/Admin | Attack payloads have Restricted/Regulated controls |
| Datasets | Retained while referenced + reproducibility window, then delete-per-policy | Min: while referenced; Max: org-configurable | Owner/Admin | Regulated/datalac may require archival |
| Reports | Configurable period per report version | Min: audit period; Max: org-configurable | Owner/Admin | Regulated may require long retention |
| Audit logs | Longest default window; append-only | Min: compliance minimum; Max: org-configurable / legal hold | Owner/Admin / data steward | Legal hold pauses deletion; permanent retention where required |

Min/max and default values are configurable per organization. The "owner role" column is the minimum role authorized to initiate deletion; Regulated data additionally requires data-steward approval.

## Storage Estimation and Cost Implications

Retention policy must be set with awareness of storage footprint (which is a cost):

- **Traces and artifacts dominate volume.** Evaluation traces are intentionally retained long as evidence; that is a deliberate cost. Production traces are where savings are found via shorter retention and sampling.
- **Immutable historical results** accumulate and are rarely pruned; plan capacity for their growth.
- **Audit logs** grow linearly and are the longest-lived class; they are cheap per row but unbounded over years.
- **Estimation.** Retention configuration should be reviewed against object-storage and trace-store capacity and cost projections. Longer retention of evaluation evidence and audit is financed by the platform's evidence guarantee; organizations should size accordingly rather than discovering cost at the storage bill.
- **Deletion frees cost but is not free of risk.** Because deletion is auditable and role-gated, purging is a deliberate, documented decision, not a background process that silently saves money at the cost of reproducibility.

## Related Documentation

- `docs/data/data-ownership.md` — how classification (including Regulated) drives these controls.
- `docs/data/data-lifecycle.md` — the lifecycle stages that end in deleted-per-policy.
- `docs/data/immutability-rules.md` — why immutable historical data may require archival instead of hard delete.
- `docs/architecture/evidence-architecture.md` — the controlled, audited deletion of evidence.
- `docs/architecture/architecture-decision-records/ADR-005` — trace retention for evaluation vs production.
- `grilling.md` Q98-Q99 — retention configurable, deletion auditable.
