"""HTTP contract of the opaque browser session (ADR-0029): the login body, the
cookie flags, the indistinguishable 401s, resolution against the database on
every request, and the idempotent logout."""
import dataclasses
import uuid
from datetime import timedelta

from domain.value_objects.agent_role import AgentRole
from tests.e2e.seeds import cookie, login, save_session, seed_agent, seed_tenant, unit_of_work


def test_login_body_is_exactly_the_authenticated_status(client):
    response = login(client, seed_agent(client).email)

    assert response.status_code == 200
    assert response.json() == {"status": "AUTHENTICATED"}


def test_login_sets_the_session_cookie_with_browser_flags(client):
    raw = login(client, seed_agent(client).email).headers.get("set-cookie", "")

    assert "leads_session=" in raw
    assert "HttpOnly" in raw
    assert "SameSite=lax" in raw
    assert "Path=/" in raw
    assert "Max-Age=28800" in raw
    assert "Secure" not in raw


def test_login_response_carries_no_token(client):
    response = login(client, seed_agent(client).email)

    token = response.cookies.get("leads_session")
    assert token
    assert "access_token" not in response.text
    assert "token_type" not in response.text
    assert token not in response.text


def test_secure_flag_follows_configuration(client, monkeypatch):
    container = client.app.state.container
    monkeypatch.setattr(container, "settings", dataclasses.replace(container.settings, session_cookie_secure=True))

    response = login(client, seed_agent(client).email)

    assert "Secure" in response.headers.get("set-cookie", "")


def test_login_failures_are_indistinguishable(client):
    """Unknown account, wrong password, inactive account and the machine role all
    answer the same 401, so no response leaks whether an account exists."""
    active = seed_agent(client)
    responses = [
        login(client, f"nobody_{uuid.uuid4().hex[:8]}@test.com"),
        login(client, active.email, "wrong-password"),
        login(client, seed_agent(client, is_active=False).email),
        login(client, seed_agent(client, role=AgentRole.INTEGRATION).email),
    ]

    assert {response.status_code for response in responses} == {401}
    assert {response.json()["error_code"] for response in responses} == {"INVALID_CREDENTIALS"}
    assert len({response.json()["message"] for response in responses}) == 1


def test_valid_cookie_reaches_me_and_a_protected_route(client):
    tenant = seed_tenant(client)
    agent = seed_agent(client, tenant_id=tenant.id.value)
    headers = cookie(login(client, agent.email).cookies["leads_session"])

    me = client.get("/api/v1/auth/me", headers=headers)
    agents = client.get("/api/v1/agents", headers=headers)

    assert me.status_code == 200
    assert me.json() == {
        "id": str(agent.id), "name": agent.name, "email": agent.email, "role": "MANAGER",
        "tenant_id": str(tenant.id), "tenant_name": tenant.name, "mfa_enabled": False,
        "linked_oauth_providers": [],
    }
    assert agents.status_code == 200


def test_the_admin_has_no_organization_in_me(client):
    admin = seed_agent(client, role=AgentRole.ADMIN, tenant_id=None)

    me = client.get("/api/v1/auth/me", headers=cookie(save_session(client, admin))).json()

    assert (me["role"], me["tenant_id"], me["tenant_name"]) == ("ADMIN", None, None)


def test_missing_tampered_and_unknown_cookies_are_unauthorized(client):
    token = login(client, seed_agent(client).email).cookies["leads_session"]
    client.cookies.clear()

    missing = client.get("/api/v1/auth/me")
    tampered = client.get("/api/v1/auth/me", headers=cookie(token + "x"))
    unknown = client.get("/api/v1/auth/me", headers=cookie("never-issued-value"))

    assert (missing.status_code, tampered.status_code, unknown.status_code) == (401, 401, 401)
    assert unknown.json()["error_code"] == "UNAUTHORIZED"


def test_expired_session_is_unauthorized_even_with_an_active_agent(client):
    """Expired rows are inserted directly: waiting eight hours is not a test strategy."""
    token = save_session(client, seed_agent(client), expires_in=-timedelta(hours=1))

    assert client.get("/api/v1/auth/me", headers=cookie(token)).status_code == 401


def test_deactivated_agent_loses_access_without_touching_the_session(client):
    agent = seed_agent(client)
    token = login(client, agent.email).cookies["leads_session"]
    with unit_of_work(client) as uow:
        agent.is_active = False
        uow.agents.save(agent)

    assert client.get("/api/v1/auth/me", headers=cookie(token)).status_code == 401


def test_an_agent_of_a_suspended_organization_is_locked_out_even_if_active(client):
    tenant = seed_tenant(client, is_active=False)
    agent = seed_agent(client, tenant_id=tenant.id.value)

    assert client.get("/api/v1/auth/me", headers=cookie(save_session(client, agent))).status_code == 401


def test_logout_revokes_and_is_idempotent(client):
    headers = cookie(login(client, seed_agent(client).email).cookies["leads_session"])
    client.cookies.clear()

    first = client.post("/api/v1/auth/logout", headers=headers)
    reuse = client.get("/api/v1/auth/me", headers=headers)
    repeated = client.post("/api/v1/auth/logout", headers=headers)
    anonymous = client.post("/api/v1/auth/logout")

    assert first.status_code == 204
    assert "leads_session" in first.headers.get("set-cookie", "")
    assert "leads_mfa_challenge" in first.headers.get("set-cookie", "")
    assert reuse.status_code == 401
    assert (repeated.status_code, anonymous.status_code) == (204, 204)
