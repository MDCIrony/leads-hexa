import uuid

from fastapi.testclient import TestClient

from infrastructure.main import app


def _bootstrap_admin(client: TestClient) -> str:
    response = client.post(
        "/api/v1/agents",
        json={
            "name": "Platform Admin",
            "email": f"admin_{uuid.uuid4().hex[:6]}@platform.test",
            "team": "HQ",
            "password": "admin-pass-123",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["role"] == "ADMIN"
    login = client.post(
        "/api/v1/auth/login",
        data={"username": response.json()["email"], "password": "admin-pass-123"},
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def _create_tenant(client: TestClient, admin_token: str, name: str, email: str) -> dict:
    response = client.post(
        "/api/v1/tenants",
        json={
            "name": name,
            "manager": {"name": "Manager", "email": email, "password": "manager-pass-123"},
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _manager_token(client: TestClient) -> str:
    admin_token = _bootstrap_admin(client)
    email = f"manager_{uuid.uuid4().hex[:6]}@acme.test"
    _create_tenant(client, admin_token, "Acme Corp", email)
    return _login(client, email, "manager-pass-123")


def test_a_list_valued_rule_survives_the_round_trip(test_db):
    """The IN operator never fired because value was coerced to str."""
    with TestClient(app) as client:
        manager_token = _manager_token(client)
        created = client.post(
            "/api/v1/rules/scoring",
            headers={"Authorization": f"Bearer {manager_token}"},
            json={
                "name": "Sectores objetivo", "field": "industry", "operator": "IN",
                "value": ["tech", "finance"], "score_delta": 40,
            },
        )
        assert created.status_code == 201

        listed = client.get(
            "/api/v1/rules/scoring", headers={"Authorization": f"Bearer {manager_token}"}
        )
        rule = next(r for r in listed.json() if r["name"] == "Sectores objetivo")
        assert rule["value"] == ["tech", "finance"]


def test_a_numeric_rule_keeps_its_number(test_db):
    with TestClient(app) as client:
        manager_token = _manager_token(client)
        created = client.post(
            "/api/v1/rules/scoring",
            headers={"Authorization": f"Bearer {manager_token}"},
            json={
                "name": "Presupuesto alto", "field": "budget", "operator": "GREATER_THAN",
                "value": 5000, "score_delta": 30,
            },
        )
        assert created.status_code == 201
        assert created.json()["value"] == 5000


def test_a_field_outside_the_allow_list_is_refused(test_db):
    with TestClient(app) as client:
        manager_token = _manager_token(client)
        refused = client.post(
            "/api/v1/rules/scoring",
            headers={"Authorization": f"Bearer {manager_token}"},
            json={
                "name": "Fuga", "field": "tenant_id", "operator": "EQUALS",
                "value": "x", "score_delta": 10,
            },
        )
        assert refused.status_code == 400
        assert refused.json()["error_code"] == "FIELD_NOT_SCORABLE"
