"""SDK error hierarchy: stable exception types mapped from HTTP status codes.

The AEGIS API returns a uniform ``{"detail": str}`` envelope. Every transport
failure the SDK raises derives from :class:`AegisError`, so downstream code can
catch one base type, then switch on the specific subclasses below.
"""

from __future__ import annotations


class AegisError(Exception):
    """Base class for every error raised by the AEGIS SDK."""


class AuthorizationError(AegisError):
    """The caller lacks a valid token or the required permission (401/403)."""


class NotFoundError(AegisError):
    """The requested resource does not exist or is outside the tenant (404)."""


class ValidationError(AegisError):
    """The request payload or query failed validation (422)."""


class ConflictError(AegisError):
    """The operation conflicts with the resource's current state (409)."""


class ServerError(AegisError):
    """The API failed internally (5xx); the request may be retried safely."""


class AegisErrorMapping:
    """Translate an HTTP status code into the matching SDK exception type."""

    @staticmethod
    def for_status(status_code: int) -> type[AegisError]:
        if status_code in (401, 403):
            return AuthorizationError
        if status_code == 404:
            return NotFoundError
        if status_code == 422:
            return ValidationError
        if status_code == 409:
            return ConflictError
        if 500 <= status_code < 600:
            return ServerError
        return AegisError


__all__ = [
    "AegisError",
    "AegisErrorMapping",
    "AuthorizationError",
    "ConflictError",
    "NotFoundError",
    "ServerError",
    "ValidationError",
]