"""Centralised exception handling. Every error uses the same JSON shape:

    {"error": {"code": "<machine_code>", "message": "<human text>", "details": [...optional]}}
"""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("findback")


class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details=None):
        self.status_code, self.code, self.message, self.details = status_code, code, message, details


def bad_request(msg, code="bad_request"): return AppError(400, code, msg)
def unauthorized(msg="Authentication required."): return AppError(401, "unauthorized", msg)
def forbidden(msg="You do not have permission to do this."): return AppError(403, "forbidden", msg)
def not_found(msg="Resource not found."): return AppError(404, "not_found", msg)
def conflict(msg, code="conflict"): return AppError(409, code, msg)
def unprocessable(msg, details=None): return AppError(422, "validation_error", msg, details)


def _body(code, message, details=None):
    err = {"code": code, "message": message}
    if details:
        err["details"] = details
    return {"error": err}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        return JSONResponse(_body(exc.code, exc.message, exc.details), exc.status_code, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        details = [{"field": ".".join(str(p) for p in e["loc"] if p not in ("body", "query", "form")),
                    "message": e["msg"]} for e in exc.errors()]
        return JSONResponse(_body("validation_error", "Request validation failed.", details), 422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        return JSONResponse(_body("http_error", str(exc.detail)), exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        log.exception("Unhandled error")
        return JSONResponse(_body("internal_error", "Internal server error."), 500)
