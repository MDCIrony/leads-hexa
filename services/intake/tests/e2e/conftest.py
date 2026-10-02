from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from application.use_cases.tenants.provision_tenant_sources import ProvisionTenantSourcesUseCase
from infrastructure.adapters.input.api.dependencies import get_container
from infrastructure.config.settings import ApiSettings
from infrastructure.di.container import Container
from infrastructure.main import app
from tests.e2e.fake_lead_core import FakeLeadCore
from tests.e2e.gateway import GatewayClient, as_principal
from tests.tokens import bearer, jwks, mint_token


@pytest.fixture
def lead_core() -> FakeLeadCore:
    return FakeLeadCore()


@pytest.fixture
def container(test_db, lead_core):
    container = Container(ApiSettings.from_environment(), jwks_fetch=jwks)
    # The one adapter that would leave the process; everything else is the production wiring.
    container.lead_admission = lead_core
    # TestClient outside a `with` does not run the lifespan: the app gets the
    # test's container, not one built from the environment.
    app.dependency_overrides[get_container] = lambda: container
    yield container
    app.dependency_overrides.clear()
    container.close()


@pytest.fixture
def client(container) -> GatewayClient:
    return GatewayClient(app, container)


@pytest.fixture
def direct_client(container) -> TestClient:
    """Straight to the app, no gateway: for what the service must hold on its own."""
    return TestClient(app)


@dataclass(frozen=True)
class Organization:
    tenant_id: UUID
    manager: dict
    agent: dict
    # The manager's own Authorization header, for calls that skip the gateway.
    direct: dict


@pytest.fixture
def organization(container):
    """Makes an organization with its default sources, as the tenants consumer does."""

    def _make() -> Organization:
        tenant_id = uuid4()
        with container.unit_of_work() as uow:
            ProvisionTenantSourcesUseCase().apply({"tenant_id": str(tenant_id), "is_active": True}, uow)
        return Organization(
            tenant_id=tenant_id,
            manager=as_principal(uuid4(), tenant_id),
            agent=as_principal(uuid4(), tenant_id, "AGENT"),
            direct=bearer(mint_token(uuid4(), tenant_id, "MANAGER")),
        )

    return _make
