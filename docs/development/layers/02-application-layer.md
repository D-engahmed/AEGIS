# Layer 02: Application

## 1. Purpose

The application layer orchestrates use cases that apply the domain model. It coordinates domain services, repositories, and infrastructure adapters to fulfill business workflows. It contains no raw SQL, no HTTP framework logic, and no queue implementation details.

## 2. Responsibilities

- Use case orchestration (creating experiments, starting evaluations, processing results).
- Transaction management (unit-of-work pattern for multi-entity operations).
- Workflow orchestration (coordinating evaluation runs, analysis, and gate decisions).
- Authorization decisions (checking permissions before executing domain operations).
- Calling interfaces between domain services and infrastructure adapters.

## 3. Non-Responsibilities

- Raw SQL or database query construction (infrastructure layer).
- HTTP framework logic such as request parsing or response serialization (interface layer).
- Queue implementation details such as message format or broker connection (execution layer).
- Provider SDK logic such as LLM API calls (evaluation layer).

## 4. Public Interfaces

Application services, command/query objects, and DTOs. These are consumed by the interface layer (03) and by the execution layer (05).

## 5. Inputs

Commands from the interface layer, triggers from the execution layer, and domain events from the domain layer.

## 6. Outputs

Application-level responses (DTOs), domain state changes, and coordination signals to infrastructure adapters.

## 7. Internal Components

- Application services (ExperimentService, EvaluationService, AnalysisService, PolicyService).
- Command and query objects (CreateExperiment, StartEvaluation, GetExperimentResult).
- DTOs (ExperimentDTO, ResultDTO) using Pydantic for validation.
- Unit-of-work abstractions for transaction boundaries.

## 8. Allowed Dependencies

- Domain layer (01).
- Pydantic (for DTOs and input validation).
- Transaction and unit-of-work abstractions (interface, not concrete implementation).

## 9. Forbidden Dependencies

- Raw SQL or ORM (infrastructure layer).
- FastAPI or any HTTP framework (interface layer).
- Queue client libraries (execution layer).
- LLM provider SDKs (evaluation layer).

## 10. Why This Design

The application layer isolates business workflows from both the domain model's purity and the infrastructure's technology specifics. It provides a testable orchestration layer that can be verified without running a web server or database.

## 11. Alternatives Considered

- **Fat application layer with all business logic**: Rejected because business rules belong in the domain, not in application services.
- **Thin application layer that just passes through**: Rejected because orchestration logic (transactions, authorization, workflow) requires a dedicated layer.
- **Merged application and interface layers**: Rejected because it couples workflow orchestration to HTTP concerns.

## 12. Why Alternatives Were Rejected

Fat application layers create anemic domain models. Thin layers fail to capture workflow complexity. Merged layers couple business workflows to transport protocols.

## 13. Technology Choice

Pydantic for DTOs. Standard Python for service logic. Abstract interfaces for repository and adapter patterns.

## 14. Technology Limits

No direct database access. No HTTP handling. No queue operations. Application services call repository interfaces and adapter interfaces, never concrete implementations.

## 15. When To Use This Technology

Every use case that requires coordinating multiple domain operations, checking authorization, or managing transactions.

## 16. When NOT To Use This Technology

Pure domain logic (use domain layer). HTTP request/response handling (use interface layer). Direct infrastructure calls (use infrastructure layer).

## 17. Failure Modes

- Application logic leaks into domain entities, creating anemic models.
- Application services bypass repository interfaces and call infrastructure directly.
- Transaction boundaries are not properly managed, leading to partial state.

## 18. Security Risks

- Authorization checks skipped or implemented inconsistently.
- Application services expose sensitive data in DTOs without redaction.
- Missing input validation at the application boundary.

## 19. Performance Risks

- N+1 query patterns from improper repository usage.
- Blocking I/O in application services instead of delegating to infrastructure.
- Large DTO copies for high-volume operations.

## 20. Testing Strategy

Integration tests with mock repositories and infrastructure adapters. Application services are tested by injecting mock domain repositories and verifying the orchestration sequence. No database or HTTP server required.

## 21. Scaling Strategy

Application services are stateless and horizontally scalable. Transaction scope is bounded by unit-of-work lifetime.

## 22. Agent Rules

Before writing application code: confirm the logic is orchestration, not domain rules or infrastructure calls. After writing: verify no raw SQL, no HTTP framework imports, and no direct queue client usage.

## 23. Code Examples

Application service example:

```python
class EvaluationService:
    def __init__(self, experiment_repo, result_repo, evaluator_registry):
        self.experiment_repo = experiment_repo
        self.result_repo = result_repo
        self.evaluator_registry = evaluator_registry

    def run_evaluation(self, experiment_id: ExperimentId) -> EvaluationResult:
        experiment = self.experiment_repo.find_by_id(experiment_id)
        if experiment is None:
            raise NotFound(entity="Experiment", entity_id=experiment_id)

        evaluators = self.evaluator_registry.get_for_experiment(experiment)
        results = []
        for evaluator in evaluators:
            result = evaluator.evaluate(experiment)
            results.append(result)

        return self.result_repo.persist_results(experiment_id, results)
```

## 24. Common Implementation Mistakes

- Placing domain validation logic in application services instead of on domain entities.
- Importing SQLAlchemy models in application service files.
- Directly constructing HTTP responses in application services.
- Bypassing repository interfaces to call database adapters.
- Placing queue publish logic in application services instead of using application events.
- Missing authorization checks before executing domain operations.
