# Error Handling

## Typed Domain Exception Hierarchy

Every error in AEGIS is a typed domain exception. The hierarchy:

```
AegisError
├── NotFound
├── Conflict
├── InvalidState
├── ValidationFailed
├── InsufficientPermission
├── RetryableFailure
├── NonRetryableFailure
├── DownstreamUnavailable
└── ImmutableResourceViolation
```

Each exception carries domain concepts: the entity involved, the operation that failed, and structured context. It never carries HTTP status codes, Redis connection details, or SQL error strings.

## Domain Errors Are Not Transport Errors

Domain exceptions are raised in the domain and application layers. The interface layer catches them and maps them to HTTP status codes per `docs/api/error-contract.md`. Domain code never knows whether the caller is an HTTP client, a CLI, or a background worker.

## Agents Must Never Swallow Exceptions or Hide Errors

This is a verbatim rule. Every failure must be classified, logged, and propagated. Catching an exception and returning a default value, an empty result, or a success status is a defect.

## Failure Classification

Every failure is classified as either:

- **Retryable**: A transient error that may succeed on retry (network timeout, rate limit, temporary unavailability).
- **Deterministic**: A permanent error that will not succeed on retry (validation failure, permission denied, schema violation).

Reference `docs/architecture/failure-architecture.md` for the full classification model.

## Retries Are Bounded

Retries are bounded with exponential backoff and a maximum attempt count. There are never infinite retries. Failed AI calls can become cost explosions. Every retry policy must have a hard limit.

## Error Logging

Errors are logged with:

- `request_id` (or `execution_id` for background jobs).
- Structured context (entity type, entity ID, operation name).
- The classified exception type.
- Stack trace at `DEBUG` level, message at `ERROR` level.

## Partial Evidence Is Preserved on Failure

When an evaluation or execution fails partway through, the partial results must be persisted. A failed execution with no evidence is worse than a failed execution with partial evidence.

## Code Example: Domain Exception in Application Layer

```python
from aegis.domain.exceptions import NotFound, Conflict


class ExperimentService:
    def start_experiment(self, experiment_id: ExperimentId) -> Experiment:
        experiment = self.repository.find_by_id(experiment_id)
        if experiment is None:
            raise NotFound(entity="Experiment", entity_id=experiment_id)
        if experiment.status != ExperimentStatus.CREATED:
            raise InvalidState(
                entity="Experiment",
                entity_id=experiment_id,
                expected="CREATED",
                actual=experiment.status,
            )
        return experiment.start()
```

## Code Example: Interface Layer Mapping

```python
from fastapi import HTTPException
from aegis.domain.exceptions import NotFound, InvalidState, InsufficientPermission


@app.exception_handler(NotFound)
async def handle_not_found(request, exc):
    raise HTTPException(status_code=404, detail=exc.to_response())


@app.exception_handler(InvalidState)
async def handle_invalid_state(request, exc):
    raise HTTPException(status_code=409, detail=exc.to_response())


@app.exception_handler(InsufficientPermission)
async def handle_insufficient_permission(request, exc):
    raise HTTPException(status_code=403, detail=exc.to_response())
```

The domain never sees these HTTP status codes. The interface layer is the only place where domain exceptions become transport responses.
