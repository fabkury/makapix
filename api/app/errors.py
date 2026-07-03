"""Standardized error envelope and stable error codes for the v1 API.

Every non-2xx response from the **app-facing v1 API** is serialized as:

    { "error": { "code": "<stable_code>", "message": "...", "details": {...}? } }

`AppError` is the preferred way to raise a client-handled error with a stable,
machine-readable code. Plain `HTTPException`s still work: the global handler maps
them to a generic code derived from the HTTP status, so existing routers keep
functioning while we migrate the enumerated client-handled sites to `AppError`.

Scope: the envelope is applied only to `/v1/*` paths. Non-versioned surfaces
(hardware players, relay, pmd/umd, legacy redirects) keep FastAPI's default
`{"detail": ...}` shape so their existing contract is byte-stable. The player RPC
router emits its own `{request_id, success, error, error_code}` envelope directly
and is unaffected.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ErrorCode(StrEnum):
    """Stable, machine-readable error codes. Documented in the OpenAPI schema.

    Add new codes here (never reuse a removed name) so clients can branch on them
    without parsing human-readable messages.
    """

    # --- Generic ---
    validation_error = "validation_error"
    bad_request = "bad_request"
    unauthorized = "unauthorized"
    forbidden = "forbidden"
    not_found = "not_found"
    conflict = "conflict"
    rate_limited = "rate_limited"
    internal_error = "internal_error"

    # --- Auth / account ---
    email_not_verified = "email_not_verified"
    weak_password = "weak_password"
    token_expired = "token_expired"
    token_invalid = "token_invalid"
    account_banned = "account_banned"
    forbidden_role = "forbidden_role"
    not_owner = "not_owner"
    handle_taken = "handle_taken"

    # --- Content / upload ---
    artwork_duplicate = "artwork_duplicate"
    dimensions_invalid = "dimensions_invalid"
    file_too_large = "file_too_large"
    quota_exceeded = "quota_exceeded"
    reaction_cap_reached = "reaction_cap_reached"
    comment_too_deep = "comment_too_deep"
    # .mkpx layers-file attachments (docs/mkpx-upload/API-CONTRACT.md §3)
    mkpx_invalid = "mkpx_invalid"
    mkpx_too_large = "mkpx_too_large"


# Fallback: HTTP status -> generic ErrorCode for plain HTTPExceptions raised
# without a structured detail. Anything unmapped becomes internal_error.
_STATUS_TO_CODE: dict[int, ErrorCode] = {
    status.HTTP_400_BAD_REQUEST: ErrorCode.bad_request,
    status.HTTP_401_UNAUTHORIZED: ErrorCode.unauthorized,
    status.HTTP_403_FORBIDDEN: ErrorCode.forbidden,
    status.HTTP_404_NOT_FOUND: ErrorCode.not_found,
    status.HTTP_405_METHOD_NOT_ALLOWED: ErrorCode.bad_request,
    status.HTTP_409_CONFLICT: ErrorCode.conflict,
    413: ErrorCode.file_too_large,  # Payload Too Large (constant renamed upstream)
    422: ErrorCode.validation_error,  # Unprocessable (constant renamed upstream)
    status.HTTP_429_TOO_MANY_REQUESTS: ErrorCode.rate_limited,
}
_DEFAULT_CODE = ErrorCode.internal_error


class AppError(Exception):
    """Raise to return a stable, machine-readable error envelope.

    Example::

        raise AppError(
            ErrorCode.handle_taken,
            "That handle is already taken.",
            status.HTTP_409_CONFLICT,
            details={"handle": handle},
        )
    """

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        http_status: int = status.HTTP_400_BAD_REQUEST,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = details
        self.headers = headers


def _envelope(
    code: ErrorCode | str, message: str, details: dict[str, Any] | None
) -> dict[str, Any]:
    err: dict[str, Any] = {"code": str(code), "message": message}
    if details:
        err["details"] = details
    return {"error": err}


def error_response(
    code: ErrorCode | str,
    message: str,
    http_status: int,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Build the standard `{ "error": { ... } }` JSON response."""
    return JSONResponse(
        status_code=http_status,
        content=_envelope(code, message, details),
        headers=headers,
    )


def _is_v1(request: Request) -> bool:
    """True for app-facing v1 paths. Non-v1 surfaces keep the legacy shape."""
    path = request.url.path
    return path.startswith("/v1/") or path == "/v1"


def register_exception_handlers(app: FastAPI) -> None:
    """Install the v1 error-envelope handlers on the FastAPI app.

    For non-v1 paths the handlers reproduce FastAPI's default behavior so the
    hardware/player and legacy contracts are unchanged.
    """

    @app.exception_handler(AppError)
    async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        if not _is_v1(request):
            # During the transition, legacy root callers (web) keep the default
            # shape so raising AppError in shared code is safe before web moves.
            return JSONResponse(
                status_code=exc.http_status,
                content={"detail": exc.message},
                headers=exc.headers,
            )
        return error_response(
            exc.code, exc.message, exc.http_status, exc.details, exc.headers
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        headers = getattr(exc, "headers", None)
        if not _is_v1(request):
            # Preserve FastAPI's default shape for non-versioned surfaces.
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers=headers,
            )
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail:
            code = detail.get("code", _code_for_status(exc.status_code))
            message = detail.get("message") or ""
            details = detail.get("details")
        else:
            code = _code_for_status(exc.status_code)
            message = detail if isinstance(detail, str) else str(detail)
            details = None
        return error_response(code, message, exc.status_code, details, headers)

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = jsonable_encoder(exc.errors())
        if not _is_v1(request):
            return JSONResponse(
                status_code=422,
                content={"detail": errors},
            )
        return error_response(
            ErrorCode.validation_error,
            "Request validation failed.",
            422,
            {"errors": errors},
        )


def _code_for_status(status_code: int) -> ErrorCode:
    return _STATUS_TO_CODE.get(status_code, _DEFAULT_CODE)
