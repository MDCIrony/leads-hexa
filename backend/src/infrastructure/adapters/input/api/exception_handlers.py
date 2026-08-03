from fastapi import Request, FastAPI
from fastapi.responses import JSONResponse
from domain.exceptions import DomainException

def add_exception_handlers(app: FastAPI):
    @app.exception_handler(DomainException)
    async def domain_exception_handler(request: Request, exc: DomainException):
        """
        Captura de forma global cualquier DomainException no controlada,
        traduciéndola en una respuesta HTTP estándar 400 Bad Request
        con el código de error propio del dominio.
        """
        return JSONResponse(
            status_code=400,
            content={
                "error": True,
                "error_code": exc.error_code,
                "message": exc.message
            }
        )
