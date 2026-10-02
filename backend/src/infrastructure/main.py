from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator
from chassis.web import RequestIdMiddleware
from fastapi import FastAPI

from infrastructure.adapters.output.persistence.migration_runner import MigrationRunner
from infrastructure.adapters.input.api.lead_router import router as lead_router
from infrastructure.adapters.input.api.intake_router import router as intake_router
from infrastructure.adapters.input.api.notification_router import router as notification_router
from infrastructure.adapters.input.api.rule_router import router as rule_router
from infrastructure.adapters.input.api.agent_router import router as agent_router
from infrastructure.adapters.input.api.sales_group_router import router as sales_group_router
from infrastructure.adapters.input.api.source_router import router as source_router
from infrastructure.adapters.input.api.auth_router import router as auth_router
from infrastructure.adapters.input.api.tenant_router import router as tenant_router
from infrastructure.adapters.input.api.internal_router import router as internal_router
from infrastructure.adapters.input.api.exception_handlers import add_exception_handlers
from infrastructure.config.settings import Settings
from infrastructure.di.container import Container
from infrastructure.logging_config import configure_logging

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging()
    settings = Settings.from_environment()
    container = Container(settings)
    migrations_dir = Path(__file__).resolve().parents[2] / "migrations"
    MigrationRunner(container.database, migrations_dir).apply_pending()

    # Delivery (outbox relay, webhooks, notification consumers) runs in the
    # backend-worker process, so the API owns nothing but request handling.
    app.state.container = container
    yield
    container.database.close()

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
app.include_router(intake_router, prefix="/api/v1/intake", tags=["Intake"])
app.include_router(rule_router, prefix="/api/v1/rules", tags=["Rules"])
app.include_router(agent_router, prefix="/api/v1/agents", tags=["Agents"])
app.include_router(sales_group_router, prefix="/api/v1/groups", tags=["Groups"])
app.include_router(source_router, prefix="/api/v1/sources", tags=["Sources"])
app.include_router(auth_router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(tenant_router, prefix="/api/v1/tenants", tags=["Platform"])
app.include_router(notification_router, prefix="/api/v1/notifications", tags=["Notifications"])
app.include_router(internal_router, prefix="/internal/v1")
