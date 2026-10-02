from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from chassis.persistence import MigrationRunner
from chassis.web import RequestIdMiddleware, configure_logging
from fastapi import FastAPI

from infrastructure.adapters.input.api.errors import add_exception_handlers
from infrastructure.adapters.input.api.notifications.router import router as notifications_router
from infrastructure.config.settings import Settings
from infrastructure.di.container import Container

# /srv/services/notifications/migrations in the image, the service folder in a checkout.
_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = Settings.from_environment()
    configure_logging(settings.log_level)
    container = Container(settings)
    MigrationRunner(container.database, _MIGRATIONS_DIR).apply_pending()
    # Event consumption runs in notifications-worker; the API owns request handling only.
    app.state.container = container
    yield
    container.database.close()


app = FastAPI(title="Notifications", version="0.1.0", lifespan=lifespan)

add_exception_handlers(app)


@app.get("/health")
def health_check():
    return {"status": "ok"}


# Every response carries the request id, including the error ones.
app.add_middleware(RequestIdMiddleware)

app.include_router(notifications_router, prefix="/api/v1/notifications", tags=["Notifications"])
