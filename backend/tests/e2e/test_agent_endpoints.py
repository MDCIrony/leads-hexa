import os
import uuid
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-production")

from fastapi.testclient import TestClient
from infrastructure.main import app
from infrastructure.security.jwt_service import create_access_token
from domain.value_objects.enums import AgentRole


def _get_auth_headers() -> dict:
    from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
    db = app.state.db
    uow = PostgresUnitOfWork(db)
    with uow:
        active_agents = uow.agents.list_active()
        if active_agents:
            admin_agent = active_agents[0]
            admin_agent.role = AgentRole.ADMIN
            uow.agents.save(admin_agent)
            admin_token = create_access_token(agent_id=str(admin_agent.id), role="ADMIN", tenant_id=None)
            return {"Authorization": f"Bearer {admin_token}"}
        else:
            token = create_access_token(agent_id=str(uuid.uuid4()), role="ADMIN", tenant_id=None)
            return {"Authorization": f"Bearer {token}"}


def test_get_agent_not_found_returns_domain_error_shape():
    with TestClient(app) as client:
        headers = _get_auth_headers()
        response = client.get(f"/api/v1/agents/{uuid.uuid4()}", headers=headers)
        assert response.status_code == 404
        data = response.json()
        assert data["error"] is True
        assert data["error_code"] == "AGENT_NOT_FOUND"
        assert "message" in data


def test_create_agent_rejects_malformed_email():
    with TestClient(app) as client:
        headers = _get_auth_headers()
        response = client.post(
            "/api/v1/agents",
            json={"name": "Bad Agent", "email": "not-an-email", "team": "Sales", "password": "pass"},
            headers=headers,
        )
        assert response.status_code == 422


def test_list_agents_returns_pagination_metadata():
    with TestClient(app) as client:
        headers = _get_auth_headers()
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

