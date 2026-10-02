import uuid

from auth_helpers import admin_headers, agent_of, seed_org_manager
from gateway_client import GatewayClient
from infrastructure.main import app


def _bootstrap_admin_headers(client: GatewayClient) -> dict:
    """The platform ADMIN; organizations are identity's, so it only names the caller now."""
    return admin_headers()


def _create_org_manager_headers(client: GatewayClient, admin_headers: dict) -> dict:
    """The manager of a fresh organization that already has its default sources."""
    return seed_org_manager()


def _agent_headers(client: GatewayClient, manager_headers: dict) -> dict:
    """A plain AGENT inside the manager's organization."""
    return agent_of(manager_headers)[0]


def test_new_organization_lists_its_two_automatic_sources():
    with GatewayClient(app) as client:
        admin_headers = _bootstrap_admin_headers(client)
        manager_headers = _create_org_manager_headers(client, admin_headers)

        response = client.get("/api/v1/sources", headers=manager_headers)
        assert response.status_code == 200
        kinds = {item["kind"] for item in response.json()["items"]}
        assert kinds == {"MANUAL_FORM", "FILE_UPLOAD"}


def test_create_source_appears_in_listing():
    with GatewayClient(app) as client:
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
    with GatewayClient(app) as client:
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
    with GatewayClient(app) as client:
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
    with GatewayClient(app) as client:
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
    with GatewayClient(app) as client:
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
    with GatewayClient(app) as client:
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
    with GatewayClient(app) as client:
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
    with GatewayClient(app) as client:
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
