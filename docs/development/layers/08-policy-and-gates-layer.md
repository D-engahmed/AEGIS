# Layer 08: Policy and Gates

## 1. Purpose

The policy and gates layer interprets evaluation results and analysis reports to produce pass, warn, block, or require-override decisions. Policy must not know HTTP, database query details, or evaluator implementation.

## 2. Responsibilities

- Evaluating normalized results against policy rules.
- Producing gate decisions: PASS, WARN, BLOCK, REQUIRE_OVERRIDE.
- Supporting composite policy logic (multiple conditions combined with AND/OR).
- Enforcing non-compensatory dimensions (a safety failure cannot be compensated by quality improvement).
- Versioning policies for auditability.
- Triggering regression tests on policy changes.

## 3. Non-Responsibilities

- Computing metric scores (evaluation layer).
- Interpreting trends or clustering failures (analysis layer).
- Persisting evidence (evidence layer).
- Enforcing gate decisions at the transport level (interface layer).

## 4. Public Interfaces

`Policy.evaluate(results) -> GateDecision`. Gate decisions are consumed by the interface layer (for deployment blocking) and the execution layer (for pre-deployment checks).

## 5. Inputs

Normalized results from the evaluation layer:

```
Metric
Score
Severity
Confidence
Blocking
```

## 6. Outputs

Gate decisions:

```
PASS
WARN
BLOCK
REQUIRE_OVERRIDE
```

## 7. Internal Components

- Policy engine (evaluates rules against normalized results).
- Composite logic evaluator (AND/OR/NOT combinations).
- Non-compensatory dimension enforcer.
- Policy version manager.
- Gate decision logger.

## 8. Allowed Dependencies

- Domain layer (01) for entity types and result structures.
- Application layer (02) for configuration and orchestration interfaces.

## 9. Forbidden Dependencies

- Interface layer (03) -- policy does not handle HTTP.
- Infrastructure layer (04) -- policy does not access databases directly.
- Evaluation layer (06) -- policy receives normalized results, it does not compute them.
- Execution layer (05) -- policy decides; execution enforces.

## 10. Why This Design

Policy decisions must be deterministic and auditable. By receiving only normalized results and producing only gate decisions, the policy layer is isolated from both the evaluation implementation and the enforcement mechanism.

## 11. Alternatives Considered

- **Policy as database rules evaluated at query time**: Rejected because it couples policy to database technology and makes policy changes require schema migrations.
- **Policy as code (hardcoded conditions)**: Rejected because it prevents runtime policy configuration and versioning.
- **Policy evaluated inline during evaluation**: Rejected because policy should see the complete result set, not individual results as they arrive.

## 12. Why Alternatives Were Rejected

Database-coupled policies are fragile. Hardcoded policies are unconfigurable. Inline evaluation prevents holistic decision-making.

## 13. Technology Choice

Pure Python rule engine. Policy definitions stored as versioned configuration. No external rule engine dependency for MVP.

## 14. Technology Limits

Complex policy logic may become difficult to express in simple rule syntax. Advanced use cases may require a dedicated policy engine in the future.

## 15. When To Use This Technology

Every deployment gate, every experiment verdict, and every policy-driven alert. No gate decision is made outside this layer.

## 16. When NOT To Use This Technology

Metric computation (use evaluation layer). Regression analysis (use analysis layer). Direct enforcement of gate outcomes (use interface or execution layer).

## 17. Failure Modes

- Policy rules that are too broad, producing false BLOCK results.
- Policy rules that are too narrow, missing genuine regressions.
- Non-compensatory dimensions not enforced, allowing safety failures to be masked by quality improvements.
- Policy version drift between environments.
- Circular policy dependencies causing infinite evaluation loops.

## 18. Security Risks

- Policy definitions modified without audit trail.
- Override mechanism abused to bypass safety gates.
- Policy rules leaking information about evaluation thresholds.
- Unauthorized policy changes that weaken security gates.

## 19. Performance Risks

- Complex composite policies slowing gate evaluation.
- Policy evaluation on large result sets without optimization.
- Policy version lookups adding latency to deployment pipelines.

## 20. Testing Strategy

Unit tests for each policy rule with known pass, warn, and block scenarios. Integration tests for composite logic. Tests for non-compensatory dimension enforcement. Policy version compatibility tests.

## 21. Scaling Strategy

Policy evaluation is lightweight and scales with the number of rules, not the number of results. Materialized gate decisions for dashboard display.

## 22. Agent Rules

Before writing policy code: confirm it only consumes normalized results and produces gate decisions. After writing: verify no HTTP, database, or evaluator-specific code exists in the policy engine.

## 23. Code Examples

Policy receives normalized results:

```
Metric
Score
Severity
Confidence
Blocking
```

Policy outputs:

```
PASS
WARN
BLOCK
REQUIRE_OVERRIDE
```

Example composite policy:

```
quality >= 0.90
AND
critical_safety_failures == 0
AND
p95_latency < 3s
```

A safety failure cannot be compensated by quality improvement. This is a non-compensatory dimension.

## 24. Common Implementation Mistakes

- Coupling policy to specific evaluator implementations.
- Not versioning policy definitions, making audit impossible.
- Allowing average scores to override per-slice failures.
- Implementing policy logic in interface-layer code instead of in the policy layer.
- Missing the non-compensatory dimension enforcement.
- Overriding BLOCK decisions without proper audit trail and approval workflow.
