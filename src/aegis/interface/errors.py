"""HTTP exception handlers: map domain/security failures to RFC 7807 errors.

The wire format is `{"detail": str}` with a stable HTTP status so SDKs can map
error handling without knowing the Python exception class.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette import status

from aegis.domain import (
    AegisDomainError,
    Conflict,
    ImmutableResourceViolation,
    InsufficientPermission,
    InvalidState,
    NotFound,
    ValidationFailed,
)

_STATUS_BY_ERROR: dict[type[AegisDomainError], int] = {
    NotFound: status.HTTP_404_NOT_FOUND,
    Conflict: status.HTTP_409_CONFLICT,
    ValidationFailed: status.HTTP_422_UNPROCESSABLE_CONTENT,
    InvalidState: status.HTTP_409_CONFLICT,
    ImmutableResourceViolation: status.HTTP_409_CONFLICT,
    InsufficientPermission: status.HTTP_403_FORBIDDEN,
}


async def _domain_error_handler(request: Request, exc: Exception) -> JSONResponse:
    del request
    if not isinstance(exc, AegisDomainError):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc)},
        )
    http_status = _STATUS_BY_ERROR.get(type(exc), status.HTTP_400_BAD_REQUEST)
    return JSONResponse(status_code=http_status, content={"detail": str(exc)})


async def _validation_handler(request: Request, exc: Exception) -> JSONResponse:
    del request
    if not isinstance(exc, RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "unhandled server error"},
        )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": "request validation failed", "errors": exc.errors()},
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AegisDomainError, _domain_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_handler)


__all__ = ["register_exception_handlers"]
