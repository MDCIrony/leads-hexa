import uuid
from fastapi.testclient import TestClient
from infrastructure.main import app


def test_get_agent_not_found_returns_domain_error_shape():
    with TestClient(app) as client:
        response = client.get(f"/api/v1/agents/{uuid.uuid4()}")
        assert response.status_code == 404
        data = response.json()
        assert data["error"] is True
        assert data["error_code"] == "AGENT_NOT_FOUND"
        assert "message" in data


def test_create_agent_rejects_malformed_email():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agents",
            json={"name": "Bad Agent", "email": "not-an-email", "team": "Sales"},
        )
        assert response.status_code == 422


def test_list_agents_returns_pagination_metadata():
    with TestClient(app) as client:
        team = f"team-{uuid.uuid4()}"
        for i in range(3):
            client.post(
                "/api/v1/agents",
                json={"name": f"Agent {i}", "email": f"agent{i}@example.com", "team": team},
            )

        response = client.get(f"/api/v1/agents?team={team}&limit=2&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 2
        assert data["has_more"] is True

        response = client.get(f"/api/v1/agents?team={team}&limit=2&offset=2")
        data = response.json()
        assert len(data["items"]) == 1
        assert data["has_more"] is False
