from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from chassis.persistence import MigrationRunner, RawSqlDatabase
from chassis.web import RequestIdMiddleware, configure_logging
from fastapi import FastAPI

from infrastructure.adapters.input.api.exception_handlers import add_exception_handlers
from infrastructure.config.settings import ApiSettings

# /srv/services/intake/migrations in the image, the service folder in a checkout.
_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = ApiSettings.from_environment()
    configure_logging(settings.log_level)
    database = RawSqlDatabase(settings.database_url)
    MigrationRunner(database, _MIGRATIONS_DIR).apply_pending()
    app.state.database = database
    yield
    database.close()


app = FastAPI(title="Intake", version="0.1.0", lifespan=lifespan)

add_exception_handlers(app)


@app.get("/health")
def health_check():
    return {"status": "ok"}


# Every response carries the request id, including the error ones.
app.add_middleware(RequestIdMiddleware)

# No CORSMiddleware: origins are the gateway's to check (ADR-0032).
