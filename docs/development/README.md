# Development Documentation

This folder contains the **binding rules** for every change made to the AEGIS codebase. These are not guidelines or suggestions. Any coding agent -- human or AI -- must follow these rules literally. Ambiguity is resolved by reading the relevant docs file, not by inventing.

## What Governs What

| File | Purpose |
|---|---|
| `development-rules.md` | Global development rules that apply to every change in the repository. |
| `dependency-rules.md` | Authorized dependency sets per layer; procedure for adding new dependencies. |
| `coding-standards.md` | Language, style, naming, testing, and toolchain expectations. |
| `error-handling.md` | Typed exception hierarchy, error classification, retry policy, and interface-layer mapping. |
| `agent-development-protocol.md` | The contract any coding agent must follow before, during, and after implementing a change. |
| `layers/00-system-boundaries.md` | What belongs inside AEGIS, what is external, and what is never directly accessible. |
| `layers/01-domain-layer.md` | Pure domain model, core entities, and invariants. Zero framework imports. |
| `layers/02-application-layer.md` | Use cases, transactions, workflow orchestration, authorization decisions. |
| `layers/03-interface-layer.md` | REST API, gRPC (future), CLI, webhook surface. Contains no business logic. |
| `layers/04-infrastructure-layer.md` | Adapters for PostgreSQL, Redis, object storage, OpenTelemetry, secrets, HTTP. |
| `layers/05-execution-layer.md` | Job scheduling, worker lifecycle, retries, timeouts, sandboxing, side-effect protection. |
| `layers/06-evaluation-layer.md` | Deterministic evaluation, LLM judge, RAG/agent/safety metric plugins. |
| `layers/07-analysis-layer.md` | Regression detection, failure clustering, comparison, slicing, statistics. |
| `layers/08-policy-and-gates-layer.md` | Policy evaluation, gate decisions, composite logic, non-compensatory dimensions. |
| `layers/09-evidence-layer.md` | Provenance, traceability, artifact references, evidence linking, reproducibility. |
| `layers/10-observability-layer.md` | Telemetry for AEGIS evaluating other systems and AEGIS itself. |
| `layers/11-security-layer.md` | Auth, authz, tenancy, secrets, PII redaction, prompt injection, cross-cutting security. |

## Layer / Purpose Reference

| Layer | Purpose |
|---|---|
| 00 | System boundaries -- what is inside, outside, and never directly accessible. |
| 01 | Domain -- pure domain model and core entities, free of external concerns. |
| 02 | Application -- use cases and orchestration that apply the domain. |
| 03 | Interface -- external surface that translates requests into application calls. |
| 04 | Infrastructure -- implementations of interfaces against external technology. |
| 05 | Execution -- scheduling and running work against targets. |
| 06 | Evaluation -- computing metric results from executions and traces. |
| 07 | Analysis -- turning results into regression, failure, and comparison insights. |
| 08 | Policy and gates -- turning evidence into pass/warn/block/defer decisions. |
| 09 | Evidence -- the immutable record and provenance that underpin every score. |
| 10 | Observability -- telemetry for operating AEGIS and for AI traces. |
| 11 | Security -- authentication, authorization, tenancy, and classification. |

## How to Use These Docs

1. Before writing code, read the `agent-development-protocol.md`.
2. Read the layer file for the layer you are modifying.
3. Follow the rules in that layer file literally.
4. If a rule conflicts with another rule, escalate -- do not guess.
5. Run the validation commands described in the agent protocol before marking work complete.
