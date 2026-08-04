from fastapi import Request, FastAPI
from fastapi.responses import JSONResponse
from domain.exceptions import DomainException

def add_exception_handlers(app: FastAPI):
    @app.exception_handler(DomainException)
    async def domain_exception_handler(request: Request, exc: DomainException):
        # Each DomainException subclass carries its own status_code so that
        # not-found-style failures map to 404 and validation-style failures
        # map to 400, instead of every domain error collapsing to one code.
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": True,
                "error_code": exc.error_code,
                "message": exc.message
            }
        )
