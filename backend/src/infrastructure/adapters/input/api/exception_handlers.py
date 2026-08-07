from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from domain.exceptions import DomainException

# The domain reports what went wrong; this table decides how HTTP says it.
# Anything not listed is a client-side validation failure by default.
STATUS_BY_ERROR_CODE: dict[str, int] = {
    "AGENT_NOT_FOUND": 404,
    "INVALID_CREDENTIALS": 401,
    "UNAUTHORIZED": 401,
    "FORBIDDEN": 403,
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
