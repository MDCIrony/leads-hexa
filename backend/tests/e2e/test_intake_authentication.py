import os
import uuid

from fastapi.testclient import TestClient
from infrastructure.main import app
from application.ports.output.token_service_port import TokenClaims
from infrastructure.adapters.output.security.jwt_token_service import JwtTokenService
from domain.value_objects.enums import AgentRole

from test_lead_endpoints import _manager_auth_headers, _seed_tenant_with_sources

_PAYLOAD = {
    "first_name": "Ana",
    "last_name": "Diaz",
    "email": "ana@lead.test",
    "company": "Acme",
    "budget": 9000.0,
    "industry": "Tech",
}


def _agent_auth_headers(tenant_id: str) -> dict:
    """Same shape as _manager_auth_headers, but for a plain sales AGENT — needed
    to prove the intake endpoint refuses a valid-but-unauthorized credential,
    not just an absent one."""
    from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
    from domain.entities.agent import Agent

    db = app.state.container.database
    uow = PostgresUnitOfWork(db)
    agent = Agent.create(
        name="Sales Agent",
        email=f"agent_{uuid.uuid4().hex[:6]}@test.com",
        role=AgentRole.AGENT,
        tenant_id=tenant_id,
    )
    with uow:
        uow.agents.save(agent)

    token_service = JwtTokenService(secret=os.environ["JWT_SECRET"])
    token = token_service.issue(TokenClaims(agent_id=str(agent.id), role="AGENT", tenant_id=str(tenant_id)))
    return {"Authorization": f"Bearer {token}"}


def test_ingest_without_credential_is_rejected():
    tenant_id = str(uuid.uuid4())

    with TestClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        response = client.post("/api/v1/intake/leads/ingest", json=_PAYLOAD)
        assert response.status_code == 401


def test_ingest_with_agent_token_is_forbidden():
    tenant_id = str(uuid.uuid4())

    with TestClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        headers = _agent_auth_headers(tenant_id)
        response = client.post("/api/v1/intake/leads/ingest", json=_PAYLOAD, headers=headers)
        assert response.status_code == 403


def test_ingest_with_manager_token_lands_in_their_own_organization():
    tenant_id = str(uuid.uuid4())

    with TestClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)
        response = client.post("/api/v1/intake/leads/ingest", json=_PAYLOAD, headers=headers)
        assert response.status_code == 201
        lead_id = response.json()["lead_id"]

        detail = client.get(f"/api/v1/leads/{lead_id}", headers=headers)
        assert detail.status_code == 200
        assert detail.json()["tenant_id"] == tenant_id


def test_ingest_ignores_a_tenant_id_in_the_body_and_uses_the_token_instead():
    tenant_a = str(uuid.uuid4())
    tenant_b = str(uuid.uuid4())

    with TestClient(app) as client:
        _seed_tenant_with_sources(tenant_a)
        _seed_tenant_with_sources(tenant_b)
        headers_a = _manager_auth_headers(tenant_a)
        headers_b = _manager_auth_headers(tenant_b)

        response = client.post(
            "/api/v1/intake/leads/ingest",
            json={**_PAYLOAD, "tenant_id": tenant_b},
            headers=headers_a,
        )
        assert response.status_code == 201
        lead_id = response.json()["lead_id"]

        # Lands in A — the token's organization...
        assert client.get(f"/api/v1/leads/{lead_id}", headers=headers_a).status_code == 200
        # ...never in B, despite what the body claimed.
        assert client.get(f"/api/v1/leads/{lead_id}", headers=headers_b).status_code == 404
