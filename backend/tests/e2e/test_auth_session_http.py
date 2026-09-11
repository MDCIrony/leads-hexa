"""HTTP contract of the opaque browser session (ADR-0029, plan 01).

Exercises the router over real PostgreSQL: the login body, the cookie flags,
the indistinguishable 401s, resolution against the database on every request,
and the idempotent logout. Behaviour, never internals: no hash is compared,
no private adapter attribute is inspected.
"""
import uuid
from datetime import datetime, timedelta, timezone
from hashlib import sha256

from fastapi.testclient import TestClient

from domain.entities.agent import Agent
from domain.entities.auth_session import AuthSession
from domain.value_objects.enums import AgentRole
from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
from infrastructure.adapters.output.security.bcrypt_password_hasher import BcryptPasswordHasher
from infrastructure.main import app

_PASSWORD = "Secret123"
_HASHED = BcryptPasswordHasher().hash(_PASSWORD)


def _seed_agent(client, role=AgentRole.MANAGER, is_active=True, tenant_id=None):
    """Persist an agent with a known password. Runs inside the TestClient
    block because the container only exists for the lifespan of the app."""
    uow = PostgresUnitOfWork(client.app.state.container.database)
    agent = Agent.create(
        name="Session",
        email=f"sess_{uuid.uuid4().hex[:8]}@test.com",
        role=role,
        hashed_password=_HASHED,
        tenant_id=tenant_id or uuid.uuid4(),
        is_active=is_active,
    )
    with uow:
        uow.agents.save(agent)
    return agent


def _login(client, email, password=_PASSWORD):
    return client.post("/api/v1/auth/login", data={"username": email, "password": password})


def _headers_for(token):
    return {"Cookie": f"leads_session={token}"}


def test_login_body_is_exactly_the_authenticated_status():
    with TestClient(app) as client:
        agent = _seed_agent(client)
        response = _login(client, agent.email)
    assert response.status_code == 200
    assert response.json() == {"status": "AUTHENTICATED"}


def test_login_sets_the_session_cookie_with_browser_flags():
    with TestClient(app) as client:
        agent = _seed_agent(client)
        response = _login(client, agent.email)
    raw = response.headers.get("set-cookie", "")
    assert "leads_session=" in raw
    assert "HttpOnly" in raw
    assert "SameSite=lax" in raw
    assert "Path=/" in raw
    assert "Max-Age=28800" in raw


def test_login_response_carries_no_token():
    with TestClient(app) as client:
        agent = _seed_agent(client)
        response = _login(client, agent.email)
    token = response.cookies.get("leads_session")
    assert token
    body = response.text
    assert "access_token" not in body
    assert "token_type" not in body
    assert token not in body


def test_secure_flag_follows_configuration(monkeypatch):
    """Outside development the cookie must travel over HTTPS only; the router
    reads that switch from the container settings on every login."""
    from infrastructure.config.settings import Settings

    with TestClient(app) as client:
        agent = _seed_agent(client)
        current = client.app.state.container._settings
        monkeypatch.setattr(
            client.app.state.container,
            "_settings",
            Settings(
                database_url=current.database_url,
                mfa_encryption_key=current.mfa_encryption_key,
                session_hours=current.session_hours,
                session_cookie_secure=True,
                cors_origins=list(current.cors_origins),
            ),
        )
        response = _login(client, agent.email)
    assert "Secure" in response.headers.get("set-cookie", "")


def test_login_failures_are_indistinguishable():
    """Unknown account, wrong password, inactive account and the machine role
    all answer the same 401, so no response leaks whether an account exists."""
    unknown = f"nobody_{uuid.uuid4().hex[:8]}@test.com"
    with TestClient(app) as client:
        active = _seed_agent(client)
        inactive = _seed_agent(client, is_active=False)
        integration = _seed_agent(client, role=AgentRole.INTEGRATION)
        responses = [
            _login(client, unknown),
            _login(client, active.email, "wrong-password"),
            _login(client, inactive.email),
            _login(client, integration.email),
        ]
    assert {response.status_code for response in responses} == {401}
    assert {response.json()["error_code"] for response in responses} == {"INVALID_CREDENTIALS"}
    messages = {response.json()["message"] for response in responses}
    assert len(messages) == 1


def test_valid_cookie_reaches_me_and_a_protected_route():
    with TestClient(app) as client:
        agent = _seed_agent(client)
        token = _login(client, agent.email).cookies["leads_session"]
        headers = _headers_for(token)
        me = client.get("/api/v1/auth/me", headers=headers)
        leads = client.get("/api/v1/leads", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == agent.email
    assert leads.status_code == 200


def test_missing_tampered_and_unknown_cookies_are_unauthorized():
    with TestClient(app) as client:
        agent = _seed_agent(client)
        token = _login(client, agent.email).cookies["leads_session"]
        client.cookies.clear()
        missing = client.get("/api/v1/auth/me")
        tampered = client.get("/api/v1/auth/me", headers=_headers_for(token + "x"))
        unknown = client.get("/api/v1/auth/me", headers=_headers_for("never-issued-value"))
    assert missing.status_code == 401
    assert tampered.status_code == 401
    assert unknown.status_code == 401
    assert unknown.json()["error_code"] == "UNAUTHORIZED"


def test_expired_session_is_unauthorized_even_with_an_active_agent():
    """Expired rows are inserted directly: the suite has no controllable clock
    in the router, and waiting eight hours is not a test strategy."""
    with TestClient(app) as client:
        agent = _seed_agent(client)
        token = "expired-session-value"
        now = datetime.now(timezone.utc)
        with PostgresUnitOfWork(client.app.state.container.database) as uow:
            uow.sessions.save(AuthSession(
                sha256(token.encode()).hexdigest(), agent.id.value,
                created_at=now - timedelta(hours=9), expires_at=now - timedelta(hours=1),
            ))
        response = client.get("/api/v1/auth/me", headers=_headers_for(token))
    assert response.status_code == 401


def test_deactivated_agent_loses_access_without_touching_the_session():
    with TestClient(app) as client:
        agent = _seed_agent(client)
        token = _login(client, agent.email).cookies["leads_session"]
        with PostgresUnitOfWork(client.app.state.container.database) as uow:
            stored = uow.agents.get_by_id(agent.id.value)
            stored.is_active = False
            uow.agents.save(stored)
        response = client.get("/api/v1/auth/me", headers=_headers_for(token))
    assert response.status_code == 401


def test_identity_and_tenant_are_reloaded_from_the_database():
    with TestClient(app) as client:
        agent = _seed_agent(client)
        token = _login(client, agent.email).cookies["leads_session"]
        me = client.get("/api/v1/auth/me", headers=_headers_for(token))
    assert me.json()["tenant_id"] == str(agent.tenant_id.value)


def test_logout_revokes_and_is_idempotent():
    with TestClient(app) as client:
        agent = _seed_agent(client)
        token = _login(client, agent.email).cookies["leads_session"]
        headers = _headers_for(token)
        first = client.post("/api/v1/auth/logout", headers=headers)
        reuse = client.get("/api/v1/auth/me", headers=headers)
        repeated = client.post("/api/v1/auth/logout", headers=headers)
        anonymous = client.post("/api/v1/auth/logout")
    assert first.status_code == 204
    assert "leads_session" in first.headers.get("set-cookie", "")
    assert reuse.status_code == 401
    assert repeated.status_code == 204
    assert anonymous.status_code == 204
