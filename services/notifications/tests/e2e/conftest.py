from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from domain.notifications.kind import NotificationKind
from domain.notifications.notification import Notification
from infrastructure.adapters.input.api.dependencies import get_container
from infrastructure.config.settings import Settings
from infrastructure.di.container import Container
from infrastructure.main import app
from tests.e2e.tokens import bearer, jwks, mint_token


def _client_for(container: Container):
    # TestClient outside a `with` does not run the lifespan: the app gets the
    # test's container, not one built from the environment.
    app.dependency_overrides[get_container] = lambda: container
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        container.database.close()


@pytest.fixture
def client(test_db):
    yield from _client_for(Container(Settings.from_environment(), jwks_fetch=jwks))


@pytest.fixture
def client_without_keys(test_db):
    def unreachable() -> dict:
        raise ConnectionError("jwks endpoint is down")

    yield from _client_for(Container(Settings.from_environment(), jwks_fetch=unreachable))


@pytest.fixture
def tenant_id() -> UUID:
    return uuid4()


@pytest.fixture
def agent_id() -> UUID:
    return uuid4()


@pytest.fixture
def auth(agent_id, tenant_id) -> dict:
    return bearer(mint_token(agent_id, tenant_id))


@pytest.fixture
def seed(uow_factory, tenant_id):
    """Saves `count` unread notices for a recipient and returns them."""

    def _seed(recipient_id: UUID, count: int = 1) -> list[Notification]:
        with uow_factory() as uow:
            return [
                uow.notifications.save(Notification.create(
                    tenant_id=tenant_id, recipient_id=recipient_id,
                    kind=NotificationKind.LEAD_ASSIGNED, message=f"Notice {n}",
                ))
                for n in range(count)
            ]

    return _seed
