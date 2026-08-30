# API Conventions

This document defines the operational conventions that apply uniformly across the API: how operations map to HTTP verbs, how collections are filtered, sorted, and paginated, how conditional and idempotent requests behave, how rate limiting is signaled, and how errors are reported. These conventions are the mechanical contract on top of the resource model in `api-design.md`.

## Verb Semantics

Standard REST verb semantics apply. The API does not define non-standard verbs.

| Verb | Semantics |
|---|---|
| `GET` | Read. Safe, idempotent, no side effects. |
| `POST` | Create a sub-resource or trigger an operation that creates a side effect. Not idempotent by itself; use `Idempotency-Key` for side-effecting writes. |
| `PATCH` | Partial update of a mutable resource. Applies only the fields supplied. |
| `PUT` | Not used for updates. Prefer `PATCH`. Where a full replace is semantically required, it is modeled as `POST` to an explicit replace sub-resource. |
| `DELETE` | Delete a deletable resource. Immutable resources cannot be deleted and are rejected. |

Compatibility rules:

- `GET` and `DELETE` are idempotent: repeating the request yields the same outcome.
- `DELETE` on an already-deleted resource returns the same terminal response (for example `200`/`204` or a stable `not_found`) and never creates a side effect a second time.
- `PATCH` is applied atomically with respect to the resource's immutable fields; attempts to patch an immutable resource are rejected with `immutable_resource`.

## Collection Filtering

Collections support filtering with a consistent expression language. The exact grammar is defined per resource in the OpenAPI schema.

- Filters target top-level resource fields.
- The syntax is `filter=<field><operator><value>`, with operators such as equality (`eq`), inequality (`neq`), set membership (`in`), range (`lt`, `lte`, `gt`, `gte`), and string containment (`contains`).
- Multiple filter clauses are combined with commas or repeated `filter` parameters and are ANDed by default. OR-combination, where needed, is explicit and documented per resource.
- Filtering is always scoped by tenant context; a filter can never escape organization and project scope.
- Filtering by evidence-sensitivity fields (raw trace content, red-team data) is subject to the authorization rules in `security-architecture.md` and `authentication-and-authorization.md`.

## Field Selection

Clients may request a sparse projection of a resource with the `fields` parameter:

```text
GET /v1/projects/{project_id}/results?fields=id,score,status
```

- `fields` is a comma-separated list of top-level field names.
- Omitting `fields` returns the full representation.
- Requesting an invalid or unauthorized field produces `validation_error` (or a permission-scoped code where the field is gated).
- Sparse fields never weaken the authorization checks that would apply to the full resource.

## Sorting

Sorting is specified with the `sort` parameter:

```text
sort=created_at:desc,name:asc
```

- Each term is `field:direction`, where direction is `asc` or `desc` (default `asc`).
- Multiple sort terms are applied left to right.
- Sorting is limited to indexed fields; attempting to sort on a non-sortable field produces `validation_error`.

## Pagination

Pagination is cursor-based for large collections.

```text
GET /v1/projects/{project_id}/executions?limit=25&cursor=<opaque>
```

- **Cursor-based pagination is the default and the only supported mode for collections that can be large** (executions, results, audit events, test cases). Cursor pagination is stable: new items appended during pagination do not shift other pages.
- The `cursor` is opaque. Clients must treat it as an opaque string, echo it back exactly, and never decode or construct it.
- The first page omits `cursor`. Responses return a `next_cursor` field (or `null`) plus the page of items.
- `limit` controls the page size. Defaults and maximums are documented per resource; a reasonable default maximum is 200. Exceeding the documented maximum returns `validation_error` or clamps with an explicit indication.
- **Page-based pagination is discouraged for large collections** (offset/limit) because it is unstable under concurrent writes and can be expensive. It is not used for large collections.

## Conditional Requests

Conditional requests protect against concurrent modification and enforce immutability.

- `ETag` headers are returned for supported resources.
- `If-Match` is honored on updates and deletes: the server performs the operation only if the supplied ETag matches the current version. A mismatch returns `412 Precondition Failed` mapped to `conflict`.
- `If-None-Match` is honored where a conditional read is safe.

### Immutable Resources

Writes to immutable resources are prohibited:

- `PATCH`, `POST` (mutating sub-resources), and `DELETE` on an immutable resource are rejected with `immutable_resource`.
- The immutable set follows `write-architecture.md`: Target Versions, locked Dataset Versions, Experiment snapshots, Evaluator Versions, and historical Results.
- Immutability is enforced in the application service within the transaction boundary, not merely rejected at the controller. Clients that attempt such a write receive the rejection regardless of `If-Match`.

## Idempotency

Writes that create side effects support an idempotency contract to prevent duplicate effects on retry.

- The client supplies an `Idempotency-Key` header on side-effecting operations (for example, `POST /experiments/{id}/runs`).
- The key is a client-generated opaque string, unique within the tenant scope.
- The server persists the key with the operation result. Replaying the same key returns the original operation result without duplicating the side effect.
- Duplicate keys are resolved against the stored result; a key reused with a different request payload returns `conflict`.
- Idempotency is the client-facing guarantee; server-side uniqueness is additionally enforced by unique execution IDs and job idempotency keys as described in `write-architecture.md` and `async-execution-contract.md`.

## Request IDs

- Every HTTP response includes a `X-Request-Id` header (echoed from the request `X-Request-Id` if provided, or generated server-side).
- Request IDs propagate into error responses (the `request_id` field of the error envelope), audit records, and logs, linking a client-visible failure to server-side observability. See `error-contract.md`.

## Rate Limiting

- Rate limiting is enforced per authenticated identity and per scope (organization, project, target where configured).
- When a client exceeds a limit, the API returns `429 Too Many Requests` with the error code `rate_limited`.
- The response includes a `Retry-After` header expressing the number of seconds the client should wait before retrying.
- Rate limits and their effective values are surfaced to authorized principals; clients that respect `Retry-After` observe the documented behavior.
- Rate limiting supports the abuse controls described in `failure-architecture.md` and `security-architecture.md`.

## Error Consistency

- Every error response uses the uniform envelope defined in `error-contract.md`, with consistent top-level fields: `error.code`, `error.message`, `error.details`, and `error.request_id`.
- The HTTP status code and the machine-readable `code` are both used: the status is the transport-level classification, the code is the precise, stable, machine-readable classification.
- Clients should branch on the `code`, not on the human-readable `message`.
- Error responses never leak stack traces or internal exception details.
- Retryability is conveyed by `error.details.retryable` where applicable, consistent with the classification rules in `error-contract.md` and `failure-architecture.md`.
