import os
import uuid
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-production")
# `infrastructure.main` reads Settings at module level (for CORS), so
# DATABASE_URL must exist by import time, not just by app startup.
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgrespassword@localhost:5433/leads_test")

from fastapi.testclient import TestClient
from infrastructure.main import app
from application.ports.output.token_service_port import TokenClaims
from infrastructure.adapters.output.security.jwt_token_service import JwtTokenService
from domain.value_objects.enums import AgentRole


def _get_auth_headers(client: TestClient) -> dict:
    """Return bearer headers for a real, persisted ADMIN agent.

    `get_current_agent` looks the bearer id up in the database, so a token
    minted for a made-up id always 401s once the table is genuinely empty
    between tests. With no active agents this rides the bootstrap rule
    (first unauthenticated POST becomes ADMIN); otherwise it promotes one
    of the agents already there. Either way the id is real.
    """
    from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
    db = app.state.container.database
    uow = PostgresUnitOfWork(db)
    with uow:
        active_agents = uow.agents.list_active()
        if active_agents:
            admin_agent = active_agents[0]
            admin_agent.role = AgentRole.ADMIN
            uow.agents.save(admin_agent)
            admin_id = str(admin_agent.id)

    if not active_agents:
        bootstrap_resp = client.post(
            "/api/v1/agents",
            json={
                "name": "Bootstrap Admin",
                "email": f"bootstrap_{uuid.uuid4().hex[:6]}@test.com",
                "team": "HQ",
                "password": "bootstrap-pass-123",
            },
        )
        assert bootstrap_resp.status_code == 201
        admin_id = bootstrap_resp.json()["id"]

    token_service = JwtTokenService(secret=os.environ["JWT_SECRET"])
    admin_token = token_service.issue(TokenClaims(agent_id=admin_id, role="ADMIN", tenant_id=None))
    return {"Authorization": f"Bearer {admin_token}"}


def _manager_auth_headers(client: TestClient) -> dict:
    """`list_agents` and `get_agent` are scoped to the caller's organization
    (§7.3), so exercising them now requires a real Manager created through
    the platform plane rather than the all-reaching Admin `_get_auth_headers`
    used to provide.
    """
    bootstrap_resp = client.post(
        "/api/v1/agents",
        json={
            "name": "Platform Admin",
            "email": f"admin_{uuid.uuid4().hex[:6]}@test.com",
            "team": "HQ",
            "password": "admin-pass-123",
        },
    )
    assert bootstrap_resp.status_code == 201
    admin_login = client.post(
        "/api/v1/auth/login",
        data={"username": bootstrap_resp.json()["email"], "password": "admin-pass-123"},
    )
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    manager_email = f"manager_{uuid.uuid4().hex[:6]}@test.com"
    tenant_resp = client.post(
        "/api/v1/tenants",
        json={
            "name": f"Org {uuid.uuid4().hex[:6]}",
            "manager": {"name": "Manager", "email": manager_email, "password": "manager-pass-123"},
        },
        headers=admin_headers,
    )
    assert tenant_resp.status_code == 201

    manager_login = client.post(
        "/api/v1/auth/login",
        data={"username": manager_email, "password": "manager-pass-123"},
    )
    assert manager_login.status_code == 200
    return {"Authorization": f"Bearer {manager_login.json()['access_token']}"}


def test_get_agent_not_found_returns_domain_error_shape():
    with TestClient(app) as client:
        headers = _manager_auth_headers(client)
        response = client.get(f"/api/v1/agents/{uuid.uuid4()}", headers=headers)
        assert response.status_code == 404
        data = response.json()
        assert data["error"] is True
        assert data["error_code"] == "AGENT_NOT_FOUND"
        assert "message" in data


def test_create_agent_rejects_malformed_email():
    with TestClient(app) as client:
        headers = _get_auth_headers(client)
        response = client.post(
            "/api/v1/agents",
            json={"name": "Bad Agent", "email": "not-an-email", "team": "Sales", "password": "pass"},
            headers=headers,
        )
        assert response.status_code == 422


def test_list_agents_returns_pagination_metadata():
    with TestClient(app) as client:
        headers = _manager_auth_headers(client)
        team = f"team-{uuid.uuid4()}"
        for i in range(3):
            client.post(
                "/api/v1/agents",
                json={
                    "name": f"Agent {i}",
                    "email": f"agent{i}_{uuid.uuid4().hex[:6]}@example.com",
                    "team": team,
                    "password": "password123",
                },
                headers=headers,
            )

        response = client.get(f"/api/v1/agents?team={team}&limit=2&offset=0", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 2
        assert data["has_more"] is True

        response = client.get(f"/api/v1/agents?team={team}&limit=2&offset=2", headers=headers)
        data = response.json()
        assert len(data["items"]) == 1
        assert data["has_more"] is False

