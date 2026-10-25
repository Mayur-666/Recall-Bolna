from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code = 400
    code = "bad_request"
    message = "Bad request."

    def __init__(self, message: str | None = None, **details: Any) -> None:
        super().__init__(message or self.message)
        self.message = message or self.message
        self.details = details


class AuthError(AppError):
    status_code = 401
    code = "unauthorized"
    message = "Not authenticated."


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"
    message = "Not allowed."


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"
    message = "Not found."


class ConflictError(AppError):
    status_code = 409
    code = "conflict"
    message = "Conflict."


class PayloadTooLargeError(AppError):
    status_code = 413
    code = "payload_too_large"
    message = "Upload is too large."


class ValidationAppError(AppError):
    status_code = 422
    code = "validation_error"
    message = "Invalid input."


class RateLimitError(AppError):
    status_code = 429
    code = "rate_limited"
    message = "Too many requests."


class UpstreamError(AppError):
    status_code = 502
    code = "upstream_error"
    message = "An upstream service failed."


def _body(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    err: dict[str, Any] = {"code": code, "message": message}
    if details:
        err["details"] = details
    return {"error": err}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(_body(exc.code, exc.message, exc.details), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Echo field locations and messages only, never the submitted values.
        fields = [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]
        return JSONResponse(_body("validation_error", "Invalid input.", {"fields": fields}), status_code=422)
