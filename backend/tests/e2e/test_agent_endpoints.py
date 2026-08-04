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
