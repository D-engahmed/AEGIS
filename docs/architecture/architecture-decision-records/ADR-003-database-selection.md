# ADR-003: Database Selection (PostgreSQL, Redis, Object Storage) - Status: Accepted

## Status

Accepted

## Date

2026-08-30

## Context

AEGIS must store several qualitatively different kinds of data:

- **Relational metadata and results**: users, projects, targets, experiments, runs,
  metrics, and results. These records have strong relationships (an experiment owns
  runs, a run produces metric results and traces), carry invariants such as
  organization/project ownership, and are the backbone of reproducibility and the
  Evidence Graph.
- **Large artifacts**: datasets, trace payloads, reports, and other binary or bulky
  objects that do not belong in a row.
- **Operational state**: the job queue, caching, distributed locks, and rate limits.

The storage architecture in `grilling.md` and README §13 draws a clean three-way split:

- **PostgreSQL** — users, projects, targets, experiments, runs, metrics, results.
- **Object storage** — large datasets, trace payloads, reports, artifacts.
- **Redis** — queue, caching, distributed locks, rate limits.

The tenants question (Q80-Q84) establishes that every tenant-owned persistent object
carries explicit owner identity and that database isolation controls plus PostgreSQL
RLS are a strong candidate for SaaS tenant isolation. The relational model is therefore
not incidental to AEGIS; it is the mechanism by which provenance, immutability, and
tenant isolation are enforced.

## Decision

AEGIS uses three storage technologies for distinct workloads:

1. **PostgreSQL** for transactional metadata and results, including users, projects,
   targets, experiments, runs, metrics, and results.
2. **Redis** for the job queue, caching, distributed locks, and rate limits.
3. **Object storage** for large artifacts, including large datasets, trace payloads,
   reports, and other blobs.

PostgreSQL is the single source of truth for relational state. It provides ACID
transactions for the invariants that reproducibility depends on (for example, immutable
historical dataset and target versions, and atomic creation of executions with their
results). It is the candidate host for PostgreSQL Row-Level Security (RLS) as a
defense-in-depth tenant-isolation control per grilling.md Q82-Q84.

## Consequences

### Positive

- **Single source of truth for relational state.** One well-understood transactional
  store holds the schema that underpins experiments, runs, results, and the Evidence
  Graph, with referential integrity and transactions.
- **ACID for write invariants.** Immutability of versioned datasets and targets, and
  consistent linkage of executions to results, are enforceable atomically.
- **RLS as a tenant-isolation candidate.** PostgreSQL RLS provides a strong,
  database-enforced isolation control complementary to application-level authorization
  (Q82-Q85).
- **Lean Postgres.** Object storage absorbs large blobs (datasets, trace payloads,
  reports), keeping tables small and indexed lookups fast.

### Negative

- **Very high write volume.** Traces and metric results can be produced at high volume
  during evaluation. Storing all of it relationally requires partitioning and aggressive
  indexing; the high-volume span path is deliberately separated into a dedicated trace
  store (ADR-005) to keep Postgres from becoming the bottleneck.
- **Specialized trace requirements.** Postgres is not a purpose-built span store; the
  trace data model is handled separately (ADR-005), which adds a second write path that
  must be kept consistent by linking on execution/trace ID.
- **Not a streaming store.** Low-latency, high-throughput event distribution is out of
  scope and remains the domain of the queue decision (ADR-002) and, later, a stream
  platform if needed.

## Alternatives Rejected

- **MongoDB-first** — the relational invariants (ownership, versioning, provenance,
  referential integrity) are core to the platform; a document store would force these to
  be re-implemented in application code.
- **Kafka-sourced event store as the primary DB** — treats all state as a log, which
  complicates the transactional relational invariants the Evidence Graph needs; no
  demonstrated need justifies that complexity (see ADR-002).
- **Wide-column stores** — optimize for a scan-heavy, denormalized access pattern that
  does not match the relational, relationship-heavy core; no evidence of need.

## When to Revisit

Revisit when measured saturation (partitioning limits, write-throughput ceiling,
locking contention on results) is reached, or when new Query patterns for evaluation
data (for example, high-cardinality analytical scans over results) demand a different
store. Any change must preserve the relational invariants that reproducibility and the
Evidence Graph depend on.

## Linked Documents

- grilling.md Q77-Q86 (multi-tenancy, RLS), §13 storage architecture (README §13)
- docs/requirements/functional-requirements.md FR-TRC, FR-EVD (trace/results linkage)
- docs/architecture/high-level-architecture.md
- docs/architecture/data-flow, docs/data/
- Supersedes nothing; related to ADR-002 (Redis queue) and ADR-005 (dedicated trace store)
