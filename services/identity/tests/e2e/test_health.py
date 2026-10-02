from fastapi.testclient import TestClient

from infrastructure.main import app


def test_the_app_starts_applies_its_migrations_and_answers_health():
    # Entering the client runs the lifespan, which migrates before serving.
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-ID": "probe-1"})

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-request-id"] == "probe-1"
