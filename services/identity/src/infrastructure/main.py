from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from chassis.persistence import MigrationRunner
from chassis.web import RequestIdMiddleware, configure_logging
from fastapi import FastAPI

from infrastructure.adapters.input.api.agents.router import router as agents_router
from infrastructure.adapters.input.api.auth.mfa_router import router as mfa_router
from infrastructure.adapters.input.api.auth.oauth_router import router as oauth_router
from infrastructure.adapters.input.api.auth.session_router import router as session_router
from infrastructure.adapters.input.api.exception_handlers import add_exception_handlers
from infrastructure.adapters.input.api.tenants.router import router as tenants_router
from infrastructure.adapters.input.internal.router import router as internal_router
from infrastructure.config.settings import ApiSettings
from infrastructure.di.container import Container

# /srv/services/identity/migrations in the image, the service folder in a checkout.
_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = ApiSettings.from_environment()
    configure_logging(settings.log_level)
    container = Container(settings)
    MigrationRunner(container.database, _MIGRATIONS_DIR).apply_pending()
    # The outbox relay runs in identity-worker; the API owns request handling only.
    app.state.container = container
    yield
    container.database.close()


app = FastAPI(title="Identity", version="0.1.0", lifespan=lifespan)

add_exception_handlers(app)


@app.get("/health")
def health_check():
    return {"status": "ok"}


# Every response carries the request id, including the error ones.
app.add_middleware(RequestIdMiddleware)

# No CORSMiddleware: origins are the gateway's to check (ADR-0032), as in the backend.
for auth_router in (session_router, mfa_router, oauth_router):
    app.include_router(auth_router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(agents_router, prefix="/api/v1/agents", tags=["Agents"])
app.include_router(tenants_router, prefix="/api/v1/tenants", tags=["Platform"])
app.include_router(internal_router, prefix="/internal/v1")
