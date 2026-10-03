from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator
from chassis.persistence import MigrationRunner
from chassis.web import RequestIdMiddleware
from fastapi import FastAPI

from infrastructure.adapters.input.api.leads.router import router as lead_router
from infrastructure.adapters.input.api.rules.scoring_router import router as rule_router
from infrastructure.adapters.input.api.advisors.router import router as advisors_router
from infrastructure.adapters.input.api.groups.router import router as sales_group_router
from infrastructure.adapters.input.api.exception_handlers import add_exception_handlers
from infrastructure.adapters.input.internal.admissions_router import router as admissions_router
from infrastructure.config.settings import ApiSettings
from infrastructure.di.container import Container
from infrastructure.logging_config import configure_logging

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = ApiSettings.from_environment()
    configure_logging(settings.log_level)
    container = Container(settings)
    migrations_dir = Path(__file__).resolve().parents[2] / "migrations"
    MigrationRunner(container.database, migrations_dir).apply_pending()

    # Delivery (outbox relay, webhooks) runs in the backend-worker process,
    # so the API owns nothing but request handling.
    app.state.container = container
    yield
    container.close()

app = FastAPI(
    title="Lead Router Platform",
    description="Plataforma Hexagonal de Scoring y Enrutamiento de Leads",
    version="0.1.0",
    lifespan=lifespan,
)

add_exception_handlers(app)

@app.get("/health")
def health_check():
    return {"status": "ok"}


# Every response carries the request id, including the error ones.
app.add_middleware(RequestIdMiddleware)

# Include Routers
app.include_router(lead_router, prefix="/api/v1/leads", tags=["Leads"])
app.include_router(rule_router, prefix="/api/v1/rules", tags=["Rules"])
app.include_router(advisors_router, prefix="/api/v1/advisors", tags=["Advisors"])
app.include_router(sales_group_router, prefix="/api/v1/groups", tags=["Groups"])
# Outside /api/v1: service to service, never through the gateway.
app.include_router(admissions_router, prefix="/internal/v1/admissions")
