import uuid

from tests.e2e.seeds import PASSWORD, bootstrap_admin, create_agent, create_organization, login
from tests.e2e.tokens import bearer, mint_token

_AGENT_KEYS = {"id", "name", "email", "is_active", "role", "tenant_id"}


def _manager(client) -> dict:
    return create_organization(client, bootstrap_admin(client))[1]


def test_get_agent_not_found_returns_domain_error_shape(client):
    response = client.get(f"/api/v1/agents/{uuid.uuid4()}", headers=_manager(client))

    assert response.status_code == 404
    data = response.json()
    assert data["error"] is True
    assert data["error_code"] == "AGENT_NOT_FOUND"
    assert "message" in data


def test_create_agent_rejects_malformed_email(client):
    response = create_agent(client, _manager(client), email="not-an-email")

    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"


def test_agent_bodies_reject_group_id_and_responses_no_longer_carry_it(client):
    headers = _manager(client)
    created = create_agent(client, headers)
    with_group = create_agent(client, headers, group_id=str(uuid.uuid4()))
    patched = client.patch(
        f"/api/v1/agents/{created.json()['id']}", json={"group_id": None}, headers=headers,
    )
    legacy_field = create_agent(client, headers, team="Sales")

    assert set(created.json()) == _AGENT_KEYS
    for response in (with_group, patched, legacy_field):
        assert response.status_code == 422
        assert response.json()["error_code"] == "VALIDATION_ERROR"
    assert with_group.json()["details"][0]["field"] == "group_id"


def test_list_agents_returns_pagination_metadata(client):
    headers = _manager(client)
    for _ in range(3):
        assert create_agent(client, headers).status_code == 201

    # The manager is one of the organization's four agents.
    first = client.get("/api/v1/agents?limit=2&offset=0", headers=headers).json()
    last = client.get("/api/v1/agents?limit=2&offset=2", headers=headers).json()

    assert (first["total"], len(first["items"]), first["has_more"]) == (4, 2, True)
    assert (len(last["items"]), last["has_more"]) == (2, False)
    assert set(first["items"][0]) == _AGENT_KEYS


def test_create_agent_rejects_duplicate_email_in_same_tenant(client):
    headers = _manager(client)
    email = f"dup_{uuid.uuid4().hex[:6]}@example.com"
    assert create_agent(client, headers, email=email).status_code == 201

    second = create_agent(client, headers, email=f"  {email.upper()} ")

    assert second.status_code == 400
    assert second.json()["error_code"] == "EMAIL_ALREADY_EXISTS"


def test_create_agent_rejects_duplicate_email_across_tenants(client):
    admin = bootstrap_admin(client)
    _, first_org = create_organization(client, admin)
    _, second_org = create_organization(client, admin)
    email = f"cross_{uuid.uuid4().hex[:6]}@example.com"
    assert create_agent(client, first_org, email=email).status_code == 201

    # Login resolves accounts by email alone, so uniqueness is platform-wide.
    second = create_agent(client, second_org, email=email)

    assert second.status_code == 400
    assert second.json()["error_code"] == "EMAIL_ALREADY_EXISTS"


def test_reactivating_an_agent_restores_login_and_default_listing(client):
    headers = _manager(client)
    email = f"reactivate_{uuid.uuid4().hex[:6]}@example.com"
    agent_id = create_agent(client, headers, email=email).json()["id"]

    deactivated = client.delete(f"/api/v1/agents/{agent_id}", headers=headers)
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False
    assert login(client, email).status_code == 401

    default_list = client.get("/api/v1/agents", headers=headers).json()
    inactive_list = client.get("/api/v1/agents?is_active=false", headers=headers).json()
    assert agent_id not in [a["id"] for a in default_list["items"]]
    assert [a["id"] for a in inactive_list["items"]] == [agent_id]
    assert inactive_list["total"] == 1
    assert default_list["total"] == len(default_list["items"])

    reactivated = client.patch(f"/api/v1/agents/{agent_id}", json={"is_active": True}, headers=headers)
    assert reactivated.status_code == 200
    assert reactivated.json()["is_active"] is True

    # Reactivating restores real login access, not just the database flag.
    relogin = login(client, email)
    assert relogin.status_code == 200
    assert relogin.json() == {"status": "AUTHENTICATED"}
    client.cookies.clear()
    assert agent_id in [a["id"] for a in client.get("/api/v1/agents", headers=headers).json()["items"]]


def test_patch_without_is_active_leaves_activation_state_untouched(client):
    headers = _manager(client)
    agent_id = create_agent(client, headers).json()["id"]

    response = client.patch(f"/api/v1/agents/{agent_id}", json={"name": "Bruno R."}, headers=headers)

    assert response.status_code == 200
    assert (response.json()["name"], response.json()["is_active"]) == ("Bruno R.", True)


def test_agents_of_another_organization_read_as_not_found(client):
    admin = bootstrap_admin(client)
    _, first_org = create_organization(client, admin)
    _, second_org = create_organization(client, admin)
    agent_id = create_agent(client, first_org).json()["id"]

    responses = [
        client.get(f"/api/v1/agents/{agent_id}", headers=second_org),
        client.patch(f"/api/v1/agents/{agent_id}", json={"is_active": True}, headers=second_org),
        client.delete(f"/api/v1/agents/{agent_id}", headers=second_org),
    ]

    assert {r.status_code for r in responses} == {404}
    assert {r.json()["error_code"] for r in responses} == {"AGENT_NOT_FOUND"}


def test_agent_role_cannot_manage_agents(client):
    headers = _manager(client)
    created = create_agent(client, headers)
    agent_headers = {"Cookie": f"leads_session={login(client, created.json()['email']).cookies['leads_session']}"}
    client.cookies.clear()

    patch = client.patch(f"/api/v1/agents/{created.json()['id']}", json={"is_active": True}, headers=agent_headers)
    listing = client.get("/api/v1/agents", headers=agent_headers)

    assert (patch.status_code, listing.status_code) == (403, 403)


def test_the_admin_manages_no_organization_and_a_manager_mints_no_admin(client):
    admin = bootstrap_admin(client)
    _, manager = create_organization(client, admin)

    assert client.get("/api/v1/agents", headers=admin).status_code == 403
    assert create_agent(client, admin).status_code == 403
    assert create_agent(client, manager, role="ADMIN").status_code == 403
    assert create_agent(client, manager, role="INTEGRATION").status_code == 403


def test_issuing_an_integration_credential_without_kafka_fails_atomically(client):
    """identity-test has no reachable broker: a failed provisioning must never
    leave an orphaned integration agent behind."""
    headers = _manager(client)

    response = client.post("/api/v1/agents/integration-credential", headers=headers)

    assert response.status_code == 503
    assert response.json()["error_code"] == "MESSAGING_UNAVAILABLE"
    agents = client.get("/api/v1/agents?is_active=true", headers=headers).json()["items"]
    assert all(a["role"] != "INTEGRATION" for a in agents)


def test_a_machine_bearer_never_creates_or_lists_agents(direct):
    # Even on an empty platform, where an anonymous call would bootstrap the admin.
    machine = bearer(mint_token(tenant_id=uuid.uuid4(), role="INTEGRATION", ptype="integration"))

    created = direct.post(
        "/api/v1/agents", json={"name": "X", "email": "x@x.test", "password": PASSWORD}, headers=machine,
    )
    listed = direct.get("/api/v1/agents", headers=machine)

    assert (created.status_code, listed.status_code) == (401, 401)
    assert created.json()["error_code"] == "UNAUTHORIZED"
