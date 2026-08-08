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


def test_platform_admin_creates_organizations_but_reaches_no_data():
    with TestClient(app) as client:
        admin_token = _bootstrap_admin(client)
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        created = _create_tenant(client, admin_token, "Acme Corp", "ana@acme.test")
        assert created["slug"] == "acme-corp"
        assert created["manager"]["role"] == "MANAGER"

        listed = client.get("/api/v1/tenants", headers=admin_headers)
        assert listed.status_code == 200
        assert listed.json()["total"] >= 1

        # The whole point of the phase: the platform plane reaches no data.
        assert client.get("/api/v1/leads", headers=admin_headers).status_code == 403
        assert client.get("/api/v1/agents", headers=admin_headers).status_code == 403
        assert client.get("/api/v1/rules/scoring", headers=admin_headers).status_code == 403


def test_manager_works_inside_its_organization_only():
    with TestClient(app) as client:
        admin_token = _bootstrap_admin(client)
        _create_tenant(client, admin_token, "Acme Corp", "ana@acme.test")
        _create_tenant(client, admin_token, "Other Corp", "bob@other.test")

        ana = {"Authorization": f"Bearer {_login(client, 'ana@acme.test', 'manager-pass-123')}"}

        assert client.get("/api/v1/leads", headers=ana).status_code == 200
        assert client.post("/api/v1/tenants", json={}, headers=ana).status_code == 403

        # The regression test for the cross-tenant leak: Ana sees her own
        # organization's agents and nobody else's.
        agents = client.get("/api/v1/agents", headers=ana)
        assert agents.status_code == 200
        emails = {item["email"] for item in agents.json()["items"]}
        assert emails == {"ana@acme.test"}


def test_sales_agent_cannot_list_agents_but_knows_who_it_is():
    with TestClient(app) as client:
        admin_token = _bootstrap_admin(client)
        _create_tenant(client, admin_token, "Acme Corp", "ana@acme.test")
        ana = {"Authorization": f"Bearer {_login(client, 'ana@acme.test', 'manager-pass-123')}"}

        created = client.post(
            "/api/v1/agents",
            json={
                "name": "Sales Person",
                "email": "sales@acme.test",
                "team": "Sales",
                "password": "sales-pass-123",
                "role": "AGENT",
            },
            headers=ana,
        )
        assert created.status_code == 201
        assert created.json()["tenant_id"] is not None

        sales = {"Authorization": f"Bearer {_login(client, 'sales@acme.test', 'sales-pass-123')}"}
        assert client.get("/api/v1/agents", headers=sales).status_code == 403

        me = client.get("/api/v1/auth/me", headers=sales)
        assert me.status_code == 200
        assert me.json()["role"] == "AGENT"
        assert me.json()["email"] == "sales@acme.test"
        assert me.json()["tenant_name"] == "Acme Corp"


def test_sales_agent_cannot_read_the_whole_organization_pipeline():
    """GET /leads is the manager's view of every lead in the organization.

    Belonging to the organization is not enough to read it: a sales agent
    would see its colleagues' leads. Its own view is GET /leads/mine.
    Asserted here so nobody relaxes the guard back to plain authentication,
    which is exactly how the platform Admin once slipped in."""
    with TestClient(app) as client:
        admin_token = _bootstrap_admin(client)
        _create_tenant(client, admin_token, "Acme Corp", "ana@acme.test")
        ana = {"Authorization": f"Bearer {_login(client, 'ana@acme.test', 'manager-pass-123')}"}

        created = client.post(
            "/api/v1/agents",
            json={
                "name": "Sales Person",
                "email": "sales@acme.test",
                "team": "Sales",
                "password": "sales-pass-123",
                "role": "AGENT",
            },
            headers=ana,
        )
        assert created.status_code == 201

        sales = {"Authorization": f"Bearer {_login(client, 'sales@acme.test', 'sales-pass-123')}"}
        assert client.get("/api/v1/leads", headers=sales).status_code == 403
        assert client.get("/api/v1/leads", headers=ana).status_code == 200


def test_identity_of_the_platform_admin_has_no_organization():
    with TestClient(app) as client:
        admin_token = _bootstrap_admin(client)
        me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
        assert me.status_code == 200
        assert me.json()["role"] == "ADMIN"
        assert me.json()["tenant_id"] is None
        assert me.json()["tenant_name"] is None


def test_deactivating_an_organization_locks_its_users_out():
    with TestClient(app) as client:
        admin_token = _bootstrap_admin(client)
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        created = _create_tenant(client, admin_token, "Acme Corp", "ana@acme.test")

        assert _login(client, "ana@acme.test", "manager-pass-123")

        patched = client.patch(
            f"/api/v1/tenants/{created['id']}",
            json={"is_active": False},
            headers=admin_headers,
        )
        assert patched.status_code == 200
        assert patched.json()["is_active"] is False

        denied = client.post(
            "/api/v1/auth/login",
            data={"username": "ana@acme.test", "password": "manager-pass-123"},
        )
        assert denied.status_code == 401


def test_creating_a_tenant_with_a_taken_email_leaves_nothing_behind():
    with TestClient(app) as client:
        admin_token = _bootstrap_admin(client)
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        _create_tenant(client, admin_token, "Acme Corp", "ana@acme.test")

        before = client.get("/api/v1/tenants", headers=admin_headers).json()["total"]
        clash = client.post(
            "/api/v1/tenants",
            json={
                "name": "Third Corp",
                "manager": {"name": "X", "email": "ana@acme.test", "password": "p"},
            },
            headers=admin_headers,
        )
        assert clash.status_code == 400
        after = client.get("/api/v1/tenants", headers=admin_headers).json()["total"]
        assert after == before
