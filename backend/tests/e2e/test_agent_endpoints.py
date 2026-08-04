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
