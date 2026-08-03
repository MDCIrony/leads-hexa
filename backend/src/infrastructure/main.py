import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI

from infrastructure.adapters.output.persistence.connection import RawSqlDatabase
from infrastructure.adapters.output.persistence.sqlite_unit_of_work import SqliteUnitOfWork
from infrastructure.adapters.output.persistence.raw_sql_webhook_repository import RawSqlWebhookRepository
from infrastructure.adapters.output.http.httpx_webhook_dispatcher import HttpxWebhookDispatcher
from infrastructure.adapters.output.events.in_memory_event_publisher import InMemoryEventPublisher
from infrastructure.adapters.output.parsers.pandas_file_parser import PandasFileParser
from application.handlers.webhook_event_handler import WebhookEventHandler
from domain.events.lead_events import LeadProcessedEvent
from infrastructure.adapters.input.api.lead_router import router as lead_router
from infrastructure.adapters.input.api.rule_router import router as rule_router
from infrastructure.adapters.input.api.agent_router import router as agent_router
from infrastructure.adapters.input.api.exception_handlers import add_exception_handlers

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    db_path = os.getenv("DATABASE_PATH", ":memory:")
    db = RawSqlDatabase(db_path)
    db.init_db()

    webhook_repo = RawSqlWebhookRepository(db.get_connection())
    webhook_dispatcher = HttpxWebhookDispatcher()
    event_publisher = InMemoryEventPublisher()

    webhook_handler = WebhookEventHandler(
        webhook_repo=webhook_repo,
        webhook_dispatcher=webhook_dispatcher,
    )
    event_publisher.subscribe(LeadProcessedEvent, webhook_handler.handle_lead_processed)

    file_parser = PandasFileParser()

    app.state.db = db
    app.state.event_publisher = event_publisher
    app.state.webhook_dispatcher = webhook_dispatcher
    app.state.file_parser = file_parser

    yield

    db.close()

app = FastAPI(
    title="Lead Router Platform",
    description="Plataforma Hexagonal de Scoring y Enrutamiento de Leads",
    version="0.1.0",
    lifespan=lifespan,
)

add_exception_handlers(app)

# Include Routers
app.include_router(lead_router, prefix="/api/v1/tenants/{tenant_id}/leads", tags=["Leads"])
app.include_router(rule_router, prefix="/api/v1/tenants/{tenant_id}/rules", tags=["Rules"])
app.include_router(agent_router, prefix="/api/v1/agents", tags=["Agents"])
