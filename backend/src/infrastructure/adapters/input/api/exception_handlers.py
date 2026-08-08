import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from domain.exceptions import DomainException

_LOGGER = logging.getLogger(__name__)

# The domain reports what went wrong; this table decides how HTTP says it.
# Anything not listed is a client-side validation failure by default.
STATUS_BY_ERROR_CODE: dict[str, int] = {
    "AGENT_NOT_FOUND": 404,
    "INVALID_CREDENTIALS": 401,
    "UNAUTHORIZED": 401,
    "FORBIDDEN": 403,
}

_ERROR_CODE_BY_STATUS = {
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
}

_DEFAULT_STATUS = 400


def add_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainException)
    async def domain_exception_handler(request: Request, exc: DomainException) -> JSONResponse:
        return JSONResponse(
            status_code=STATUS_BY_ERROR_CODE.get(exc.error_code, _DEFAULT_STATUS),
            content={
                "error": True,
                "error_code": exc.error_code,
                "message": exc.message,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "message": "La petición no supera la validación de esquema",
                "details": [
                    {
                        "field": ".".join(str(part) for part in error["loc"][1:]),
                        "code": error["type"],
                        "message": error["msg"],
                    }
                    for error in exc.errors()
                ],
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": True,
                "error_code": _ERROR_CODE_BY_STATUS.get(exc.status_code, "HTTP_ERROR"),
                "message": str(exc.detail),
            },
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # The message is deliberately generic: internal failures must not leak
        # database or stack details to a client.
        _LOGGER.error("Unhandled error on %s %s", request.method, request.url.path, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": True,
                "error_code": "INTERNAL_ERROR",
                "message": "Se ha producido un error interno",
            },
        )
