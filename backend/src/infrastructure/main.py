import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI

from infrastructure.adapters.output.persistence.connection import RawSqlDatabase
from infrastructure.adapters.output.persistence.raw_sql_lead_repository import RawSqlLeadRepository
from infrastructure.adapters.output.persistence.raw_sql_rule_repository import RawSqlRuleRepository
from infrastructure.adapters.output.persistence.raw_sql_agent_repository import RawSqlAgentRepository
from infrastructure.adapters.output.http.httpx_webhook_dispatcher import HttpxWebhookDispatcher
from infrastructure.adapters.output.parsers.pandas_file_parser import PandasFileParser
from application.use_cases.ingest_lead_use_case import IngestLeadUseCase
from application.use_cases.process_batch_use_case import ProcessBatchUseCase
from infrastructure.adapters.input.api.lead_router import router as lead_router
from infrastructure.adapters.input.api.rule_router import router as rule_router
from infrastructure.adapters.input.api.agent_router import router as agent_router

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    db_path = os.getenv("DATABASE_PATH", ":memory:")
    db = RawSqlDatabase(db_path)
    db.init_db()

    lead_repo = RawSqlLeadRepository(db)
    rule_repo = RawSqlRuleRepository(db)
    agent_repo = RawSqlAgentRepository(db)
    webhook_dispatcher = HttpxWebhookDispatcher()
    file_parser = PandasFileParser()

    ingest_lead_use_case = IngestLeadUseCase(
        lead_repo=lead_repo,
        rule_repo=rule_repo,
        agent_repo=agent_repo,
        webhook_dispatcher=webhook_dispatcher,
    )
    process_batch_use_case = ProcessBatchUseCase(
        file_parser=file_parser,
        ingest_lead_use_case=ingest_lead_use_case,
    )

    app.state.db = db
    app.state.lead_repo = lead_repo
    app.state.rule_repo = rule_repo
    app.state.agent_repo = agent_repo
    app.state.webhook_dispatcher = webhook_dispatcher
    app.state.file_parser = file_parser
    app.state.ingest_lead_use_case = ingest_lead_use_case
    app.state.process_batch_use_case = process_batch_use_case

    yield

    db.close()

app = FastAPI(
    title="Lead Router Platform",
    description="Plataforma Hexagonal de Scoring y Enrutamiento de Leads",
    version="0.1.0",
    lifespan=lifespan,
)

# Include Routers
app.include_router(lead_router, prefix="/api/v1/tenants/{tenant_id}/leads", tags=["Leads"])
app.include_router(rule_router, prefix="/api/v1/tenants/{tenant_id}/rules", tags=["Rules"])
app.include_router(agent_router, prefix="/api/v1/agents", tags=["Agents"])
