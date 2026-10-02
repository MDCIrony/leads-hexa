import uuid

from tests.e2e.seeds import PASSWORD, bootstrap_admin, create_agent, create_organization, login


def test_creating_an_organization_returns_it_with_its_manager(client):
    admin = bootstrap_admin(client)

    body, _ = create_organization(client, admin)

    assert set(body) == {"id", "name", "slug", "is_active", "created_at", "agent_count", "manager"}
    assert body["is_active"] is True
    assert body["agent_count"] is None
    assert set(body["manager"]) == {"id", "name", "email", "is_active", "role", "tenant_id"}
    assert (body["manager"]["role"], body["manager"]["tenant_id"]) == ("MANAGER", body["id"])


def test_an_organization_name_or_manager_email_already_in_use_is_rejected(client):
    admin = bootstrap_admin(client)
    body, _ = create_organization(client, admin)

    same_name = client.post(
        "/api/v1/tenants",
        json={"name": body["name"], "manager": {"name": "M", "email": "new@x.test", "password": PASSWORD}},
        headers=admin,
    )
    same_email = client.post(
        "/api/v1/tenants",
        json={"name": "Another", "manager": {"name": "M", "email": body["manager"]["email"], "password": PASSWORD}},
        headers=admin,
    )

    assert (same_name.status_code, same_name.json()["error_code"]) == (400, "TENANT_ALREADY_EXISTS")
    assert (same_email.status_code, same_email.json()["error_code"]) == (400, "EMAIL_ALREADY_EXISTS")


def test_listing_counts_active_agents_newest_first(client):
    admin = bootstrap_admin(client)
    older, manager = create_organization(client, admin)
    newer, _ = create_organization(client, admin)
    create_agent(client, manager)

    page = client.get("/api/v1/tenants", headers=admin).json()

    assert (page["total"], page["has_more"]) == (2, False)
    assert [item["id"] for item in page["items"]] == [newer["id"], older["id"]]
    assert [item["agent_count"] for item in page["items"]] == [1, 2]
    assert all(item["manager"] is None for item in page["items"])


def test_suspending_an_organization_locks_its_agents_out(client):
    admin = bootstrap_admin(client)
    body, manager = create_organization(client, admin)

    suspended = client.patch(f"/api/v1/tenants/{body['id']}", json={"is_active": False}, headers=admin)

    assert suspended.status_code == 200
    assert suspended.json()["is_active"] is False
    assert client.get("/api/v1/agents", headers=manager).status_code == 401
    assert login(client, body["manager"]["email"]).status_code == 401


def test_renaming_keeps_the_slug_and_an_unknown_organization_is_not_found(client):
    admin = bootstrap_admin(client)
    body, _ = create_organization(client, admin)

    renamed = client.patch(f"/api/v1/tenants/{body['id']}", json={"name": "Renamed"}, headers=admin)
    missing = client.patch(f"/api/v1/tenants/{uuid.uuid4()}", json={"name": "Nobody"}, headers=admin)

    assert (renamed.json()["name"], renamed.json()["slug"]) == ("Renamed", body["slug"])
    assert (missing.status_code, missing.json()["error_code"]) == (404, "TENANT_NOT_FOUND")


def test_only_the_platform_admin_reaches_the_platform_plane(client):
    admin = bootstrap_admin(client)
    body, manager = create_organization(client, admin)

    responses = [
        client.get("/api/v1/tenants", headers=manager),
        client.patch(f"/api/v1/tenants/{body['id']}", json={"name": "Mine"}, headers=manager),
        client.post(
            "/api/v1/tenants",
            json={"name": "X", "manager": {"name": "M", "email": "m@x.test", "password": PASSWORD}},
            headers=manager,
        ),
    ]

    assert [r.status_code for r in responses] == [403, 403, 403]
    assert {r.json()["error_code"] for r in responses} == {"FORBIDDEN"}
