# Layer 00: System Boundaries

## 1. Purpose

Defines what belongs inside AEGIS, what is an external dependency, and what is never directly accessible from within the system. This layer establishes the trust boundaries that all other layers must respect.

## 2. Responsibilities

- Defining the boundary between AEGIS and external systems.
- Identifying external dependencies and their access patterns.
- Establishing trust boundaries between planes (control, execution, evidence).
- Defining what components may never directly access each other.

## 3. Non-Responsibilities

- Implementing any business logic.
- Making policy or gate decisions.
- Performing evaluation or analysis.
- Storing or retrieving data.

## 4. Public Interfaces

None. This layer is a set of rules and constraints, not code. Its artifacts are documentation, ADRs, and architectural diagrams.

## 5. Inputs

System design decisions, ADRs, and architectural reviews.

## 6. Outputs

Boundary rules, trust boundary definitions, and access constraints that all other layers enforce.

## 7. Internal Components

- Trust boundary definitions (control plane, execution plane, evidence plane).
- External system registry (PostgreSQL, Redis, object storage, LLM providers, target AI systems).
- Access constraint rules (verbatim below).

## 8. Allowed Dependencies

None. This layer defines rules; it does not import code.

## 9. Forbidden Dependencies

All. This layer is pure documentation and constraint definition.

## 10. Why This Design

System boundaries prevent accidental coupling between internal and external concerns. Without explicit boundaries, layers will reach across to external systems, creating fragility, security holes, and testing difficulty.

## 11. Alternatives Considered

- **No explicit boundaries, rely on code review**: Rejected because boundaries are invisible in code review without documentation.
- **Boundary enforcement via lint rules**: Considered for future implementation, but documentation is the baseline.

## 12. Why Alternatives Were Rejected

Code review without documented boundaries fails at scale. Lint rules are a reinforcement mechanism, not a replacement for explicit definitions.

## 13. Technology Choice

Documentation and ADR format only.

## 14. Technology Limits

None. This layer has no runtime footprint.

## 15. When To Use This Technology

Always. Boundary decisions are made before any code is written.

## 16. When NOT To Use This Technology

Never. Every architectural change must be checked against boundary rules.

## 17. Failure Modes

- Boundary violations go undetected, leading to coupling between planes.
- External systems are accessed directly from domain code, breaking purity.
- Trust boundaries are bypassed, creating security gaps.

## 18. Security Risks

- Unauthorized access to external systems from within AEGIS.
- Cross-plane access that bypasses authorization checks.
- External system credentials exposed in domain or application layers.

## 19. Performance Risks

None. This layer has no runtime component.

## 20. Testing Strategy

Boundary compliance is verified by import analysis (lint rules that detect forbidden imports in domain code) and by architectural review.

## 21. Scaling Strategy

Not applicable.

## 22. Agent Rules

Agents must check boundary rules before implementing any cross-component access. If a proposed change crosses a boundary, stop and propose an ADR.

## 23. Code Examples

Not applicable. This layer is rule-based, not code-based.

## 24. Common Implementation Mistakes

- Importing infrastructure code (SQLAlchemy, Redis client) directly in domain modules.
- Calling external LLM providers from application services without going through the evaluation layer.
- Allowing the execution layer to modify policy definitions.
- Letting the dashboard (interface layer) directly query the database without going through application services.
- Treating boundary documentation as optional reading.

## Access Constraints (Verbatim)

```
Dashboard
    cannot directly access Database

Evaluator
    cannot directly access Control Plane

Worker
    cannot modify policy definitions

Target Adapter
    cannot decide gate outcomes
```

These constraints apply regardless of implementation convenience. If a shortcut across a boundary seems necessary, record an ADR justifying the exception.
