# ADR-005: Dedicated Trace Storage Strategy - Status: Accepted

## Status

Accepted

## Date

2026-08-30

## Context

AEGIS must trace AI execution with a richer model than a plain observability system.
A trace captures user input, LLM generation (model, prompt, completion, tokens,
latency), retrieval (query, retrieved documents, scores), tool calls (name, arguments,
result, error), agent decisions, memory events, guardrails, and errors (grilling.md
Q453; README §6). Internally a trace is a tree of spans.

Two properties make trace storage a distinct architectural concern:

- **Traces are evidence, not telemetry to be sampling-dropped.** Evaluation traces must
  NOT be sampled away (Q474: "Normally no; production observability may use sampling").
  They are the raw material of the Evidence Graph: "No score without evidence." Traces
  link to evaluation results and to evidence (Q470; FR-TRC-07; FR-EVD-03).
- **Traces are high-volume and privacy-sensitive.** They contain prompts and outputs
  (Q455-Q457), which are configurable and subject to PII redaction and secret detection
  before storage (Q458-Q461). Their volume and shape do not match transactional
  relational rows in PostgreSQL.

The guidance is to prefer OpenTelemetry-compatible semantics rather than inventing a
proprietary trace format (Q454; README §6 "OpenTelemetry-compatible model where
practical"; FR-OBS-01), while keeping the capability to model evaluation-only semantics
on top. OpenTelemetry should not be the entire data model (Q34-Q35); AEGIS also owns
datasets, experiments, verdicts, policies, regressions, and governance.

## Decision

Traces are stored in a **dedicated trace store** with **OpenTelemetry-compatible
semantics**, kept separate from transactional metadata in PostgreSQL. Large objects and
artifacts (payloads, retrieved documents, report bodies) live in object storage as
referenced by the trace spans.

The trace is part of the **Evidence Graph**: a trace links to an execution, and the
execution links to results and scores. The invariant is "No score without evidence" —
every score is backed by the execution context from which it was derived.

The dedicated trace store is the second write path for execution data. It must remain
consistent with PostgreSQL transactional metadata by linking traces to executions on a
stable execution/trace ID.

For the long term, prefer an **OpenTelemetry collector** that forwards into a compatible
backend (for example a store with OTLP support) rather than reinventing a trace format
and transport. Sampling remains available **only for production observability**, never
for evaluation evidence.

## Consequences

### Positive

- **Independent scaling and retention.** High-volume span data scales and is retained
  separately from relational metadata, avoiding the governance conflicts that would
  arise from mixing the two (see ADR-003).
- **Semantic compatibility.** OpenTelemetry-compatible spans interoperate with the
  broader observability ecosystem rather than creating an isolated telemetry universe
  (Q33).
- **Evidence integrity preserved.** Because evaluation traces are never sampled away,
  the Evidence Graph stays complete and every score remains defensible.
- **Privacy as a first-class concern.** The trace store is where configurable prompt/
  output capture and PII/secret redaction are enforced before persistence (FR-TRC-03,
  FR-TRC-04).

### Negative

- **A second write path to keep consistent.** Traces are written to the trace store in
  parallel with transactional state in PostgreSQL; the two must be reconciled by linking
  on execution/trace ID, adding integration and consistency work.
- **Operational surface.** Operating a second storage technology (and later an OTel
  collector and backend) adds deployment, monitoring, and failure-handling burden.
- **Dual schema.** Trace structure and relational structure evolve separately, requiring
  disciplined schema management in each store.

## Alternatives Rejected

- **Store traces only in PostgreSQL rows** — high-volume span data would saturate the
  transactional store and distort its access patterns (see ADR-003).
- **Invent a proprietary trace format and store from scratch** — ignores the guidance to
  prefer OpenTelemetry-compatible semantics (Q454) and the ecosystem interop benefit.
- **Make OpenTelemetry the entire data model** — telemetry describes execution but not
  evaluation datasets, experiments, verdicts, and governance (Q34-Q35).

## When to Revisit

Revisit when scale demands a dedicated vendor backend (for example, a hosted OTLP
service with its own scaling, retention, and cost model) or when the cost profile of
self-hosting the trace store changes materially. The decision may be revised to adopt a
managed OpenTelemetry backend while preserving the semantics and the "no sampling of
evaluation evidence" guarantee.

## Linked Documents

- grilling.md Q453-Q475 (trace model, OpenTelemetry preference, sampling, privacy)
- README.md §6 (trace model)
- docs/requirements/functional-requirements.md FR-TRC-01 .. FR-TRC-04, FR-TRC-07,
  FR-EVD-01, FR-EVD-03, FR-OBS-01, FR-OBS-03
- docs/architecture/evidence, docs/architecture/data-flow, docs/data/
- Related to ADR-003 (separates trace store from PostgreSQL)
