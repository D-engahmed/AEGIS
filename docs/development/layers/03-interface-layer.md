# Layer 03: Interface

## 1. Purpose

The interface layer is the external surface of AEGIS. It translates incoming requests into application-layer calls and returns responses. It contains no business logic.

## 2. Responsibilities

- REST API endpoints (FastAPI).
- gRPC service definitions (future).
- CLI commands.
- Webhook receivers and senders.
- Request validation (transport shape, not business rules).
- Response formatting (HTTP status codes, response bodies).
- Authentication middleware delegation (to security layer).

## 3. Non-Responsibilities

- Business logic and domain rules (application and domain layers).
- Database queries (infrastructure layer).
- Evaluation computation (evaluation layer).
- Policy decisions (policy and gates layer).
- Job scheduling (execution layer).

## 4. Public Interfaces

REST endpoints, gRPC service stubs, CLI entry points, and webhook contracts. These are the only externally visible surfaces of AEGIS.

## 5. Inputs

HTTP requests, gRPC calls, CLI arguments, and webhook payloads.

## 6. Outputs

HTTP responses, gRPC responses, CLI output, and webhook payloads.

## 7. Internal Components

- FastAPI application and router definitions.
- Request/response schemas (Pydantic models for API contracts).
- Middleware (authentication, rate limiting, request ID injection).
- Exception handlers that map domain exceptions to HTTP status codes.

## 8. Allowed Dependencies

- FastAPI (REST framework).
- Pydantic (request/response schemas).
- Auth middleware (from security layer 11).
- Application layer (02).

## 9. Forbidden Dependencies

- Domain layer (01) -- must go through application layer.
- Infrastructure layer (04) -- no direct database or cache access.
- Evaluation layer (06) -- no direct metric computation.
- Provider SDKs -- no direct LLM API calls.

## 10. Why This Design

The interface layer ensures that external consumers interact with AEGIS through a well-defined contract. By containing no business logic, it remains thin, testable, and swappable (REST today, gRPC tomorrow, GraphQL later).

## 11. Alternatives Considered

- **Fat controllers with business logic in route handlers**: Rejected because it couples transport to business rules.
- **GraphQL from day one**: Deferred; REST is sufficient for MVP and can be extended later.
- **Merged interface and application layers**: Rejected because it prevents independent testing of HTTP handling vs. business logic.

## 12. Why Alternatives Were Rejected

Fat controllers make business logic untestable without an HTTP server. GraphQL adds complexity before the domain model is stable. Merged layers prevent separation of concerns.

## 13. Technology Choice

FastAPI for REST API. Pydantic for schema validation. Standard ASGI server (uvicorn) for runtime.

## 14. Technology Limits

FastAPI is the HTTP framework. No other HTTP framework (Django, Flask) is used. The interface layer must not accumulate business logic regardless of framework capabilities.

## 15. When To Use This Technology

Every external API endpoint, webhook, and CLI command that receives or returns data.

## 16. When NOT To Use This Technology

Internal service-to-service communication within AEGIS goes through application-layer interfaces, not HTTP endpoints. Domain logic never passes through this layer.

## 17. Failure Modes

- Business logic creeps into route handlers, making it untestable in isolation.
- Domain exceptions are not mapped, resulting in raw 500 errors.
- Request validation is incomplete, allowing malformed data to reach the application layer.
- Response shapes change without contract review, breaking API consumers.

## 18. Security Risks

- Missing authentication middleware on protected endpoints.
- Verbose error responses that expose internal implementation details.
- Missing rate limiting allowing abuse.
- Request ID not propagated, making incident response difficult.

## 19. Performance Risks

- Synchronous route handlers blocking the event loop.
- Large response payloads without pagination.
- Missing response compression for large datasets.

## 20. Testing Strategy

Endpoint-level tests using FastAPI's TestClient. No database or external service required. Mock application services to verify request routing and response formatting. Validate OpenAPI schema generation.

## 21. Scaling Strategy

Stateless HTTP handlers, horizontally scalable behind a load balancer. Connection pooling managed at the infrastructure layer.

## 22. Agent Rules

Before writing interface code: confirm the logic is request routing and response formatting, not business logic. After writing: verify no domain rules, no database access, and no direct external service calls exist in route handlers.

## 23. Code Examples

Request flow:

```
Input
↓
Validate Transport Shape
↓
Call Application
↓
Return Response
```

## 24. Common Implementation Mistakes

- Placing business logic in FastAPI route handlers.
- Importing domain entities directly without going through application services.
- Returning raw database models as API responses.
- Not mapping domain exceptions to structured HTTP error responses.
- Missing request ID middleware, making debugging impossible.
- Changing API response shapes without contract review.
- Hardcoding authentication logic instead of delegating to security middleware.
