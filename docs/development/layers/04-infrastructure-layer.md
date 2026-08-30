# Layer 04: Infrastructure

## 1. Purpose

The infrastructure layer implements adapters that connect AEGIS to external technologies. It provides concrete implementations of repository interfaces, cache interfaces, and external service clients defined by the application and domain layers.

## 2. Responsibilities

- PostgreSQL access via SQLAlchemy (repository implementations).
- Redis operations (queue client, cache, distributed locks).
- Object storage operations (S3-compatible storage for large artifacts).
- OpenTelemetry integration (trace export, metric export).
- External HTTP clients (for calling target AI systems).
- Secrets provider access (Vault, cloud KMS).

## 3. Non-Responsibilities

- Business logic and domain rules (domain layer).
- Use case orchestration (application layer).
- HTTP request handling (interface layer).
- Job scheduling and worker lifecycle (execution layer).
- Metric computation (evaluation layer).
- Gate decisions (policy and gates layer).

## 4. Public Interfaces

Repository implementations, cache adapters, storage clients, telemetry exporters, and secrets clients. These implement interfaces defined by the application layer.

## 5. Inputs

Interface objects from the application layer (repository interfaces, adapter contracts).

## 6. Outputs

Persisted data, cached values, exported telemetry, fetched external data, and retrieved secrets.

## 7. Internal Components

- SQLAlchemy models and repository implementations.
- Redis client wrappers (queue, cache, locks).
- Object storage client (upload, download, presigned URLs).
- OpenTelemetry trace and metric exporters.
- HTTP client wrappers with retry, timeout, and circuit breaker logic.
- Secrets provider client with caching and rotation support.

## 8. Allowed Dependencies

- SQLAlchemy (ORM for PostgreSQL).
- Redis client (async and sync).
- Object storage client (boto3 or equivalent).
- OpenTelemetry SDK (tracing, metrics).
- Secrets provider client (hvac, boto3 secretsmanager, or equivalent).
- HTTP clients (httpx, aiohttp).

## 9. Forbidden Dependencies

- Domain exceptions or business rules -- infrastructure adapters implement interfaces, they do not decide business outcomes.
- Interface layer (FastAPI) -- infrastructure does not handle HTTP requests.
- Evaluation or analysis logic -- infrastructure provides data, it does not interpret it.

## 10. Why This Design

Infrastructure adapters isolate the rest of AEGIS from technology specifics. Swapping PostgreSQL for a different database, Redis for a different cache, or changing the LLM provider requires changes only in this layer.

## 11. Alternatives Considered

- **Direct ORM usage in application services**: Rejected because it couples application logic to database technology.
- **Repository pattern without interfaces**: Rejected because it prevents mocking and testing.
- **Infrastructure layer as a shared kernel**: Rejected because it creates circular dependencies.

## 12. Why Alternatives Were Rejected

Direct ORM in application services breaks testability. Missing interfaces prevent isolation testing. Shared kernels create coupling.

## 13. Technology Choice

SQLAlchemy for PostgreSQL. Redis-py for Redis. boto3-compatible clients for object storage. OpenTelemetry SDK for telemetry. httpx for HTTP clients.

## 14. Technology Limits

Infrastructure adapters must not contain business logic. They transform between domain/application interfaces and technology-specific APIs. If an adapter grows complex, it should be decomposed rather than accumulating logic.

## 15. When To Use This Technology

Every interaction with PostgreSQL, Redis, object storage, external HTTP services, secrets providers, or telemetry backends.

## 16. When NOT To Use This Technology

Domain logic, application orchestration, interface handling, and evaluation computation never use infrastructure technology directly.

## 17. Failure Modes

- Repository implementations leak database-specific error handling into application code.
- Cache invalidation bugs cause stale data to be served.
- Telemetry exporter failures cause application failures (should degrade gracefully).
- Secrets provider outages block all authenticated operations.

## 18. Security Risks

- Database credentials exposed in code or logs.
- Redis connections without authentication.
- Object storage buckets with overly permissive access policies.
- Secrets provider tokens not rotated.
- HTTP clients that do not verify TLS certificates.

## 19. Performance Risks

- N+1 query patterns in repository implementations.
- Missing connection pooling.
- Cache stampedes from missing TTL or lock mechanisms.
- Unbounded query results without pagination.
- Telemetry export blocking application threads.

## 20. Testing Strategy

Integration tests against real or containerized databases and caches. Repository implementations tested with test fixtures. Telemetry exporters tested with mock backends. HTTP clients tested with recorded responses or mock servers.

## 21. Scaling Strategy

Connection pooling for PostgreSQL. Redis cluster mode for high-throughput caching. Object storage is inherently scalable. HTTP clients use connection pooling and rate limiting.

## 22. Agent Rules

Before writing infrastructure code: confirm there is an application-layer interface to implement. After writing: verify the adapter contains no business logic and only transforms between interface and technology-specific API.

## 23. Code Examples

Repository implementation pattern:

```python
class PostgresExperimentRepository:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def find_by_id(self, experiment_id: ExperimentId) -> Experiment | None:
        with self.session_factory() as session:
            row = session.query(ExperimentModel).filter_by(id=experiment_id).first()
            if row is None:
                return None
            return row.to_domain()
```

## 24. Common Implementation Mistakes

- Placing business logic in repository implementations.
- Importing domain exceptions and raising them from infrastructure code.
- Not using connection pooling for database access.
- Blocking the event loop with synchronous database calls in async contexts.
- Logging secrets or PII in infrastructure adapter debug output.
- Not handling infrastructure-specific exceptions and wrapping them in domain exceptions.
- Bypassing the repository pattern and using raw ORM queries in application services.
