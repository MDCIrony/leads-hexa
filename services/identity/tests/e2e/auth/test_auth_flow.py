import uuid

from tests.e2e.seeds import PASSWORD, cookie, create_agent, create_organization, login, unit_of_work


def test_full_auth_flow_bootstrap_login_and_role_enforcement(client):
    # 1. Bootstrap: the first agent on an empty platform is the admin, whatever role it asks for.
    admin_email = f"admin_{uuid.uuid4().hex[:6]}@test.com"
    bootstrap = client.post(
        "/api/v1/agents", json={"name": "Root", "email": admin_email, "password": PASSWORD, "role": "AGENT"},
    )
    assert bootstrap.status_code == 201
    assert (bootstrap.json()["role"], bootstrap.json()["tenant_id"]) == ("ADMIN", None)

    # 2. Login with the bootstrap admin's real credentials sets a usable session.
    admin_login = login(client, admin_email)
    assert admin_login.status_code == 200
    admin_headers = cookie(admin_login.cookies["leads_session"])
    # Without clearing the jar every later call would carry the admin session,
    # and step 4 would test an authenticated request instead of an anonymous one.
    client.cookies.clear()

    # 3. Wrong password is rejected.
    assert login(client, admin_email, "wrong-password").status_code == 401

    # 4. The bootstrap window is closed: anonymous creation now fails, even asking for ADMIN.
    second = client.post(
        "/api/v1/agents", json={"name": "X", "email": "x@x.test", "password": PASSWORD, "role": "ADMIN"},
    )
    assert second.status_code == 401
    assert second.json()["error_code"] == "UNAUTHORIZED"

    # 5. The admin plane creates an organization together with its first manager.
    tenant, manager_headers = create_organization(client, admin_headers)
    assert tenant["manager"]["role"] == "MANAGER"

    # 6. Another organization's manager does not see the first one's agents.
    _, other_headers = create_organization(client, admin_headers)
    agent = create_agent(client, manager_headers)
    assert agent.status_code == 201
    other_ids = [a["id"] for a in client.get("/api/v1/agents", headers=other_headers).json()["items"]]
    assert agent.json()["id"] not in other_ids

    # 7. A plain AGENT is forbidden from managing agents.
    agent_headers = cookie(login(client, agent.json()["email"]).cookies["leads_session"])
    client.cookies.clear()
    assert client.get("/api/v1/agents", headers=agent_headers).status_code == 403
    assert client.get("/api/v1/auth/me", headers=agent_headers).json()["role"] == "AGENT"

    # 8. Deactivating the agent revokes its existing session at once: every
    # request resolves the identity against the database again.
    with unit_of_work(client) as uow:
        stored = uow.agents.get_by_id(uuid.UUID(agent.json()["id"]))
        stored.is_active = False
        uow.agents.save(stored)
    assert client.get("/api/v1/agents", headers=agent_headers).status_code == 401
    assert client.get("/api/v1/auth/me", headers=agent_headers).status_code == 401
