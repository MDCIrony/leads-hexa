from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from infrastructure.adapters.output.persistence.migration_runner import MigrationRunner
from infrastructure.adapters.output.persistence.raw_sql_webhook_repository import RawSqlWebhookRepository
from infrastructure.adapters.output.http.httpx_webhook_dispatcher import HttpxWebhookDispatcher
from application.handlers.webhook_event_handler import WebhookEventHandler
from domain.events.lead_events import LeadProcessedEvent
from infrastructure.adapters.input.api.lead_router import router as lead_router
from infrastructure.adapters.input.api.intake_router import router as intake_router
from infrastructure.adapters.input.api.rule_router import router as rule_router
from infrastructure.adapters.input.api.agent_router import router as agent_router
from infrastructure.adapters.input.api.auth_router import router as auth_router
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

    # Held open for the process lifetime and only ever read from, so it runs
    # in autocommit mode rather than sitting in one long-lived transaction.
    # Needs a connection with a longer lifetime than a per-request unit of
    # work, so it is built here rather than in the container. get_connection()
    # is now a pool-backed context manager, so it wraps everything up to and
    # including `yield`: the connection returns to the pool only at shutdown.
    with container.database.get_connection(autocommit=True) as webhook_connection:
        webhook_handler = WebhookEventHandler(
            webhook_repo=RawSqlWebhookRepository(webhook_connection),
            webhook_dispatcher=HttpxWebhookDispatcher(timeout=settings.webhook_timeout_seconds),
        )
        container.event_publisher.subscribe(LeadProcessedEvent, webhook_handler.handle_lead_processed)

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


# Read at module level, not inside lifespan: CORSMiddleware must be
# registered while the module is imported, before the app starts serving.
_settings = Settings.from_environment()

app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(lead_router, prefix="/api/v1/leads", tags=["Leads"])
app.include_router(intake_router, prefix="/api/v1/intake/{tenant_id}/leads", tags=["Intake"])
app.include_router(rule_router, prefix="/api/v1/rules", tags=["Rules"])
app.include_router(agent_router, prefix="/api/v1/agents", tags=["Agents"])
app.include_router(auth_router, prefix="/api/v1/auth", tags=["Auth"])
