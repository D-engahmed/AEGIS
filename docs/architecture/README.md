# Architecture Documentation

This directory is the authoritative description of how AEGIS is structured and why. It is a navigational index and a substantive reference: it defines the boundaries of the system, the planes of operation, the key architectural decisions, and the contracts that every component must honor. Before writing code in AEGIS, read the relevant sections here and the layer rules in `docs/development/layers/`.

## What This Documentation Is For

The architecture documentation exists to answer, for any proposed change, the questions: *which plane does this belong to, which boundary does it cross, which contracts must it satisfy, and which architectural decisions does it affect?* It is not a static description of the code; it is the system that keeps the code coherent.

It records four things:

- **Boundaries** — what belongs inside AEGIS, what is an external dependency, and what can never be directly accessed.
- **Planes** — the Control, Execution, and Evidence planes and the separation of authority from execution from verification.
- **Decisions** — the engineering decisions captured as Architecture Decision Records (ADRs) under `architecture-decision-records/`.
- **Contracts** — the component template, layer dependency rules, and the "No score without evidence" law that each component obeys.

## Reading Order

Read the architecture documentation in a fixed order. Each document builds on the previous one and refers forward to the ones that follow.

1. **high-level-architecture.md** — the big picture: the three planes, the modular monolith decision, the connective principle.
2. **system-context.md** — the boundary of the system and its relationships to actors and external systems.
3. **container-architecture.md** — the deployable/runnable units (containers) of the modular monolith.
4. **component-architecture.md** — the internal building blocks of the control plane and beyond, mapped to the development layers.
5. **development-architecture.md** — the layered source structure of the codebase and its dependency rules.
6. **read-architecture.md** and **write-architecture.md** — how data and control flow into and out of the system.
7. **execution-architecture.md** — how work is scheduled, run, and contained across the execution plane.
8. **evidence-architecture.md** — how traces, artifacts, results, provenance, and the evidence graph are produced and consumed.
9. **security-architecture.md** — the threat model and authorization boundaries.
10. **data-flow.md** — how data moves across planes and storage technologies.
11. **failure-architecture.md** — how the system fails contained and degrades predictably.
12. **architecture-decision-records/** — the recorded decisions that constrain all of the above.

## Component Documentation Template

Every documented component — whether it is a plane, a container, or a coarse-grained internal building block — must be described using the following template. Filling in every field is required; omitting a field is a signal that the component boundary or the decision behind it is not yet clear.

- **Responsibility** — What this component is accountable for, in one or two sentences.
- **Inputs** — The data, events, or commands this component consumes and from whom.
- **Outputs** — The data, events, or commands this component produces and to whom.
- **Dependencies** — The components, infrastructure, and external systems it requires to operate.
- **Failure Modes** — The ways this component can fail and the consequences of each.
- **Scaling Model** — How this component scales: horizontally, vertically, or not at all, and what gates its throughput.
- **Security Boundary** — What this component may and may not trust, and what it protects.
- **Why This Component Exists** — The problem its absence would create.
- **Why It Is Not Combined With Another Component** — The dependency, isolation, or authority reason that forces a separate boundary.
- **Technology Choice** — The concrete technology selected for this component.
- **Alternatives Rejected** — The realistic alternatives considered and the reason each was rejected.
- **When To Replace Technology** — The observable conditions that would justify replacing the current technology.

## Architecture Decision Records (ADRs)

Decisions that constrain the architecture are recorded as Architecture Decision Records in `docs/architecture/architecture-decision-records/`. An ADR is required for any of the following:

- Introducing, changing, or retiring a technology (database, queue, worker runtime, evaluator framework).
- Allowing a layer to reach across to a non-neighboring layer (see `development-architecture.md`).
- Changing the boundary between the Control, Execution, or Evidence planes.
- Changing the "No score without evidence" contract or the immutability guarantees of the Evidence Plane.
- Adding a new external dependency or changing the trust relationship with an existing one.

Referenced ADRs include **ADR-001** (modular monolith over premature microservices). When a new decision is made, record it as an ADR before the implementation that commits to it.

## Other Architecture Documents

- **high-level-architecture.md** — the three planes, the modular monolith decision, and the connective "No score without evidence" law.
- **system-context.md** — the system boundary: actors, external systems, and what must never be directly accessed.
- **container-architecture.md** — the deployable/runnable containers and which are packaged together initially.
- **component-architecture.md** — the internal building blocks and their layer mapping.
- **development-architecture.md** — the layered source structure and dependency direction rules.
- **read-architecture.md** and **write-architecture.md** — the read and write flows across the system.
- **execution-architecture.md** — scheduling, running, and containing execution-plane work.
- **evidence-architecture.md** — traces, artifacts, results, provenance, and the evidence graph.
- **security-architecture.md** — the threat model and authorization boundaries.
- **data-flow.md** — data movement across planes and storage technologies.
- **failure-architecture.md** — contained and predictable failure behavior.
- **architecture-decision-records/** — recorded decisions (starting with ADR-001 on the modular monolith).

Related documentation outside this directory: `docs/README.md` (overview and reading path), `docs/requirements/` (intent), `docs/development/` and `docs/implementation/` (change behavior), `docs/data/` (schema and storage), `docs/operations/` (failure and observability), and `docs/testing/` (verification).
