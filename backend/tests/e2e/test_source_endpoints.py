import uuid

from fastapi.testclient import TestClient
from infrastructure.main import app


def _bootstrap_admin_headers(client: TestClient) -> dict:
    """A fresh platform ADMIN, used only to create organizations."""
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
    login = client.post(
        "/api/v1/auth/login",
        data={"username": bootstrap_resp.json()["email"], "password": "admin-pass-123"},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _create_org_manager_headers(client: TestClient, admin_headers: dict) -> dict:
    """Bearer headers for the manager of a freshly created organization."""
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


def _agent_headers(client: TestClient, manager_headers: dict) -> dict:
    """Bearer headers for a plain AGENT inside the manager's organization."""
    email = f"agent_{uuid.uuid4().hex[:6]}@test.com"
    create_resp = client.post(
        "/api/v1/agents",
        json={"name": "Agent", "email": email, "password": "agent-pass-123"},
        headers=manager_headers,
    )
    assert create_resp.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": "agent-pass-123"},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_new_organization_lists_its_two_automatic_sources():
    with TestClient(app) as client:
        admin_headers = _bootstrap_admin_headers(client)
        manager_headers = _create_org_manager_headers(client, admin_headers)

        response = client.get("/api/v1/sources", headers=manager_headers)
        assert response.status_code == 200
        kinds = {item["kind"] for item in response.json()["items"]}
        assert kinds == {"MANUAL_FORM", "FILE_UPLOAD"}


def test_create_source_appears_in_listing():
    with TestClient(app) as client:
        admin_headers = _bootstrap_admin_headers(client)
        manager_headers = _create_org_manager_headers(client, admin_headers)

        response = client.post(
            "/api/v1/sources",
            json={"name": "Landing Page", "kind": "MANUAL_FORM"},
            headers=manager_headers,
        )
        assert response.status_code == 201
        created = response.json()
        assert created["name"] == "Landing Page"
        assert created["is_active"] is True

        listing = client.get("/api/v1/sources", headers=manager_headers).json()
        assert created["id"] in {item["id"] for item in listing["items"]}


def test_create_source_rejects_duplicate_name_in_same_organization():
    with TestClient(app) as client:
        admin_headers = _bootstrap_admin_headers(client)
        manager_headers = _create_org_manager_headers(client, admin_headers)
        name = f"Campaign {uuid.uuid4().hex[:6]}"

        first = client.post(
            "/api/v1/sources", json={"name": name, "kind": "MANUAL_FORM"}, headers=manager_headers
        )
        assert first.status_code == 201
        total_before = client.get("/api/v1/sources", headers=manager_headers).json()["total"]

        second = client.post(
            "/api/v1/sources", json={"name": name, "kind": "MANUAL_FORM"}, headers=manager_headers
        )
        assert second.status_code != 201
        assert second.json()["error_code"] == "SOURCE_ALREADY_EXISTS"

        total_after = client.get("/api/v1/sources", headers=manager_headers).json()["total"]
        assert total_after == total_before


def test_same_source_name_allowed_in_different_organization():
    with TestClient(app) as client:
        admin_headers = _bootstrap_admin_headers(client)
        manager_a_headers = _create_org_manager_headers(client, admin_headers)
        manager_b_headers = _create_org_manager_headers(client, admin_headers)
        name = f"Shared Name {uuid.uuid4().hex[:6]}"

        first = client.post(
            "/api/v1/sources", json={"name": name, "kind": "MANUAL_FORM"}, headers=manager_a_headers
        )
        assert first.status_code == 201

        second = client.post(
            "/api/v1/sources", json={"name": name, "kind": "MANUAL_FORM"}, headers=manager_b_headers
        )
        assert second.status_code == 201


def test_patch_and_delete_of_another_organizations_source_return_404():
    with TestClient(app) as client:
        admin_headers = _bootstrap_admin_headers(client)
        manager_a_headers = _create_org_manager_headers(client, admin_headers)
        manager_b_headers = _create_org_manager_headers(client, admin_headers)

        foreign_source_id = client.get("/api/v1/sources", headers=manager_a_headers).json()["items"][0]["id"]

        patch_resp = client.patch(
            f"/api/v1/sources/{foreign_source_id}",
            json={"is_active": False},
            headers=manager_b_headers,
        )
        assert patch_resp.status_code == 404
        assert patch_resp.json()["error_code"] == "SOURCE_NOT_FOUND"

        delete_resp = client.delete(f"/api/v1/sources/{foreign_source_id}", headers=manager_b_headers)
        assert delete_resp.status_code == 404
        assert delete_resp.json()["error_code"] == "SOURCE_NOT_FOUND"


def test_patch_is_active_toggles_in_both_directions():
    with TestClient(app) as client:
        admin_headers = _bootstrap_admin_headers(client)
        manager_headers = _create_org_manager_headers(client, admin_headers)

        created = client.post(
            "/api/v1/sources",
            json={"name": f"Toggle {uuid.uuid4().hex[:6]}", "kind": "MANUAL_FORM"},
            headers=manager_headers,
        ).json()
        source_id = created["id"]

        deactivated = client.patch(
            f"/api/v1/sources/{source_id}", json={"is_active": False}, headers=manager_headers
        )
        assert deactivated.status_code == 200
        assert deactivated.json()["is_active"] is False

        reactivated = client.patch(
            f"/api/v1/sources/{source_id}", json={"is_active": True}, headers=manager_headers
        )
        assert reactivated.status_code == 200
        assert reactivated.json()["is_active"] is True


def test_delete_source_without_leads_returns_204():
    with TestClient(app) as client:
        admin_headers = _bootstrap_admin_headers(client)
        manager_headers = _create_org_manager_headers(client, admin_headers)

        created = client.post(
            "/api/v1/sources",
            json={"name": f"Disposable {uuid.uuid4().hex[:6]}", "kind": "MANUAL_FORM"},
            headers=manager_headers,
        ).json()

        response = client.delete(f"/api/v1/sources/{created['id']}", headers=manager_headers)
        assert response.status_code == 204


def test_delete_source_with_a_lead_returns_source_in_use_not_500():
    with TestClient(app) as client:
        admin_headers = _bootstrap_admin_headers(client)
        manager_headers = _create_org_manager_headers(client, admin_headers)

        ingest_resp = client.post(
            "/api/v1/intake/leads/ingest",
            json={
                "first_name": "Jane",
                "last_name": "Doe",
                "company": "Acme",
                "budget": 1000.0,
                "industry": "retail",
            },
            headers=manager_headers,
        )
        assert ingest_resp.status_code == 202

        manual_form_id = next(
            item["id"]
            for item in client.get("/api/v1/sources", headers=manager_headers).json()["items"]
            if item["kind"] == "MANUAL_FORM"
        )

        response = client.delete(f"/api/v1/sources/{manual_form_id}", headers=manager_headers)
        assert response.status_code != 500
        assert response.json()["error_code"] == "SOURCE_IN_USE"


def test_agent_role_is_forbidden_from_all_four_endpoints():
    with TestClient(app) as client:
        admin_headers = _bootstrap_admin_headers(client)
        manager_headers = _create_org_manager_headers(client, admin_headers)
        agent_headers = _agent_headers(client, manager_headers)

        existing_id = client.get("/api/v1/sources", headers=manager_headers).json()["items"][0]["id"]

        assert client.get("/api/v1/sources", headers=agent_headers).status_code == 403
        assert client.post(
            "/api/v1/sources", json={"name": "x", "kind": "MANUAL_FORM"}, headers=agent_headers
        ).status_code == 403
        assert client.patch(
            f"/api/v1/sources/{existing_id}", json={"is_active": False}, headers=agent_headers
        ).status_code == 403
        assert client.delete(f"/api/v1/sources/{existing_id}", headers=agent_headers).status_code == 403
