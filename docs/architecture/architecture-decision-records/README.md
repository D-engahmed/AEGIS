# Architecture Decision Records

## What Is an Architecture Decision Record (ADR)?

An Architecture Decision Record (ADR) is a short, dated document that records a single
architectural decision: the context in which it was made, the decision itself, its
consequences, and the alternatives that were considered and rejected. It is written at
the moment the decision matters, before the implementation that commits to it, so that
the reasoning is captured while it is still fresh and honest.

An ADR is not a conversation summary. It is a binding engineering document. Once an ADR
is accepted, it becomes the rule that the architecture, the code, and future proposals
must obey until a later ADR explicitly supersedes it.

## Why AEGIS Needs ADRs

The AEGIS documentation philosophy is that the "why" of a system must be formal
architecture, not a conversation that is lost when the discussion ends. Requirements
define intent, architecture defines boundaries, and ADRs define the reasons behind the
boundaries. Probabilistic AI systems demand more discipline, not less: evaluation,
regression testing, safety gating, and evidence-based verdicting only mean something if
the design decisions behind them are explicit, contestable, and traceable.

Three problems that ADRs solve for AEGIS:

- **Why this and why not this.** Every significant technology and boundary decision has
  real alternatives (microservices, Kafka, MongoDB, in-process evaluators). The ADR
  records both the chosen option and the credible alternatives that were deliberately
  rejected, so future engineers do not silently re-litigate settled questions.
- **Institutional memory.** The reasoning in `grilling.md` is the design interrogation
  that produced these decisions. An ADR fixes that reasoning to a dated, immutable
  record that survives team changes.
- **Binding constraint.** An ADR is the mechanism by which a decision stops being an
  opinion and becomes an architectural law that later ADRs, docs, and code must respect.

## The ADR Template

Every ADR in this directory follows the same structure:

- **Title** — `ADR-00X: <Title>` followed by the status (`Accepted`, `Proposed`, or
  `Superseded`).
- **Status** — Accepted, Proposed, or Superseded. Superseded records cite the ADR that
  replaces them.
- **Date** — the date the decision was made.
- **Context** — the problem, the constraints, and the forces at play.
- **Decision** — the decision stated in precise, testable terms.
- **Consequences** — the Positive (benefits) and Negative (costs and risks) outcomes,
  and the conditions under which the decision should be revisited.
- **Alternatives Rejected** — each credible alternative with a one-line reason it was
  rejected.
- **Linked Documents** — references to `grilling.md` question numbers and to the
  architecture and requirement documents the decision affects.

## ADR Lifecycle and Proposal Process

An ADR is created through a lightweight, explicit process so that architectural change
is deliberate rather than accidental:

1. **Read existing ADRs.** Before proposing any architecture change, read the accepted
   ADRs in this directory plus the architecture documentation they constrain. A proposal
   that contradicts an accepted ADR must first justify why that ADR should be superseded.
2. **Propose a new ADR.** Write the new ADR as a `Proposed` record using the template
   above. It must state the context, the decision, the consequences, the alternatives
   rejected, and the existing ADRs or documents it affects or would change.
3. **Review and accept.** The proposed ADR is reviewed by the architecture owners and
   the reviewers responsible for the affected planes. Acceptance is explicit: the status
   changes to `Accepted` and the date is recorded.
4. **The ADR becomes binding.** Once accepted, the decision is a rule. Implementation
   follows its terms, and later proposals must treat it as a constraint until it is
   formally superseded by a new ADR.

An ADR is required for any decision that would otherwise be made implicitly in code:
introducing, changing, or retiring a technology (database, queue, worker runtime,
evaluator framework); allowing a layer to reach across to a non-neighboring layer;
changing a boundary between the Control, Execution, or Evidence planes; changing the
"No score without evidence" contract or the immutability guarantees of the Evidence
Plane; or adding a new external dependency or changing a trust relationship.

## Where New ADRs Are Added

New ADRs are added to this directory as sequential files following the existing
numbering (`ADR-00X`). The next available number is always recorded in the index table
below. Each new ADR is one self-contained file and cross-references the ADRs, the
`grilling.md` questions, and the architecture or requirement documents it touches.

## ADR Index

| ADR | Status | Summary |
|-----|--------|---------|
| ADR-001 | Accepted | Start AEGIS as a modular monolith with strict plane boundaries, not microservices; execution workers are isolated runnable processes from day one. |
| ADR-002 | Accepted | Use a Redis-backed durable job queue (Celery / Dramatiq / ARQ) for evaluation scheduling; do not adopt Kafka initially. |
| ADR-003 | Accepted | PostgreSQL for transactional metadata and results, Redis for queue/cache/locks/rate-limits, object storage for large artifacts. |
| ADR-004 | Accepted | Evaluators are plugins behind a stable interface, executed in isolation over an RPC boundary rather than imported into the control plane. |
| ADR-005 | Accepted | Store traces in a dedicated OpenTelemetry-compatible trace store, kept separate from PostgreSQL transactional metadata. |
