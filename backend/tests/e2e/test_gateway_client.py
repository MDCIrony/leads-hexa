"""GatewayClient must reproduce the gateway's trust rules, or every e2e test
that rides it proves nothing about the real stack (ADR-0031)."""
import uuid

from auth_helpers import session_headers
from domain.entities.agent import Agent
from domain.value_objects.enums import AgentRole
from gateway_client import GatewayClient
from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
from infrastructure.adapters.output.security.bcrypt_password_hasher import BcryptPasswordHasher
from infrastructure.main import app

_UNAUTHORIZED = {"error": True, "error_code": "UNAUTHORIZED", "message": "Authentication required"}
_SECRET = "gateway-secret"
_HASHED = BcryptPasswordHasher().hash(_SECRET)


def _seed(client, role, tenant_id=None, hashed_password=None) -> Agent:
    agent = Agent.create(
        name="Gateway", email=f"gw_{uuid.uuid4().hex[:8]}@test.com", role=role,
        hashed_password=hashed_password, tenant_id=tenant_id,
    )
    with PostgresUnitOfWork(client.app.state.container.database) as uow:
        uow.agents.save(agent)
    return agent


def test_a_bearer_forged_by_the_caller_is_never_trusted():
    with GatewayClient(app) as client:
        manager = _seed(client, AgentRole.MANAGER, uuid.uuid4())
        forged = client.app.state.container.token_issuer.issue(manager, "human")

        response = client.get("/api/v1/leads", headers={"Authorization": f"Bearer {forged}"})

    assert response.status_code == 401
    assert response.json() == _UNAUTHORIZED


def test_the_cookie_decides_even_when_the_caller_sends_a_manager_bearer():
    with GatewayClient(app) as client:
        tenant = uuid.uuid4()
        sales = _seed(client, AgentRole.AGENT, tenant)
        manager = _seed(client, AgentRole.MANAGER, tenant)
        forged = client.app.state.container.token_issuer.issue(manager, "human")

        response = client.get(
            "/api/v1/leads", headers={**session_headers(sales), "Authorization": f"Bearer {forged}"},
        )

    assert response.status_code == 403


def test_an_api_key_reaches_the_integration_route():
    with GatewayClient(app) as client:
        agent = _seed(client, AgentRole.INTEGRATION, uuid.uuid4(), _HASHED)

        response = client.get("/api/v1/leads", headers={"X-Api-Key": f"{agent.id}.{_SECRET}"})

    assert response.status_code == 200


def test_internal_routes_do_not_exist_from_outside():
    with GatewayClient(app) as client:
        response = client.get("/internal/v1/jwks")

    assert response.status_code == 404
    assert response.json() == {"error": True, "error_code": "NOT_FOUND", "message": "Not Found"}


def test_a_bearer_on_a_public_route_is_dropped():
    with GatewayClient(app) as client:
        manager = _seed(client, AgentRole.MANAGER, uuid.uuid4())
        forged = client.app.state.container.token_issuer.issue(manager, "human")

        # /auth/me is cookie-authenticated: the bearer must not stand in for it.
        response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {forged}"})

    assert response.status_code == 401


def test_the_first_agent_can_be_created_without_credentials():
    with GatewayClient(app) as client:
        response = client.post("/api/v1/agents", json={
            "name": "First", "email": f"first_{uuid.uuid4().hex[:6]}@test.com",
            "password": "first-pass-123",
        })

    assert response.status_code == 201
    assert response.json()["role"] == "ADMIN"
