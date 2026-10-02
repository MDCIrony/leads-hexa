from fastapi.testclient import TestClient

from infrastructure.main import app


def test_the_app_starts_applies_its_migrations_and_answers_health(test_db):
    # Entering the client runs the lifespan, which migrates before serving.
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-ID": "probe-1"})
        container = app.state.container

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-request-id"] == "probe-1"
    with test_db.get_connection(autocommit=True) as conn:
        applied = conn.execute("SELECT count(*) AS n FROM schema_migrations").fetchone()["n"]
        tables = {row["tablename"] for row in conn.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")}
    assert applied >= 5
    assert {"lead_sources", "intake_jobs", "intake_records", "outbox_events"} <= tables
    assert container.token_verifier is not None
