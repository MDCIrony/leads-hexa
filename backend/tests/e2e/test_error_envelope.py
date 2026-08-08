from fastapi.testclient import TestClient

from infrastructure.main import app

_REQUIRED_KEYS = {"error", "error_code", "message"}


def test_validation_errors_use_the_common_envelope():
    with TestClient(app) as client:
        response = client.post("/api/v1/auth/login", data={"username": "only-this"})
    assert response.status_code == 422
    body = response.json()
    assert _REQUIRED_KEYS <= set(body)
    assert body["error_code"] == "VALIDATION_ERROR"
    assert isinstance(body["details"], list)


def test_missing_credentials_use_the_common_envelope():
    with TestClient(app) as client:
        response = client.get("/api/v1/agents")
    assert response.status_code == 401
    body = response.json()
    assert _REQUIRED_KEYS <= set(body)
    assert body["error_code"] == "UNAUTHORIZED"


def test_unknown_route_uses_the_common_envelope():
    with TestClient(app) as client:
        response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert _REQUIRED_KEYS <= set(response.json())
