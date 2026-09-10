"""Origin protection for cookie writes (ADR-0029, plan 03).

A present Origin that is not exactly in CORS_ORIGINS is rejected before any
use case runs; a missing Origin stays allowed for CLIs, workers and curl.
`main._settings` is patched at module level because the middleware reads it
per request, not from the environment.
"""
import uuid
from dataclasses import replace

from fastapi.testclient import TestClient

import infrastructure.main as main_module
from domain.entities.agent import Agent
from domain.value_objects.enums import AgentRole
from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
from infrastructure.adapters.output.security.bcrypt_password_hasher import BcryptPasswordHasher
from infrastructure.main import app

_PASSWORD = "Secret123"
_HASHED = BcryptPasswordHasher().hash(_PASSWORD)
_ALLOWED = "http://localhost:5173"
_HOSTILE = "https://evil.test"


def _use_origins(monkeypatch, origins):
    monkeypatch.setattr(
        main_module, "_settings", replace(main_module._settings, cors_origins=list(origins))
    )


def _seed_manager(client):
    uow = PostgresUnitOfWork(client.app.state.container.database)
    agent = Agent.create(
        name="Origin",
        email=f"origin_{uuid.uuid4().hex[:8]}@test.com",
        role=AgentRole.MANAGER,
        hashed_password=_HASHED,
        tenant_id=uuid.uuid4(),
    )
    with uow:
        uow.agents.save(agent)
    return agent


def _login(client, email, origin=None):
    headers = {"Origin": origin} if origin else {}
    return client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": _PASSWORD},
        headers=headers,
    )


def _session_count(client, agent):
    with client.app.state.container.database.get_connection(autocommit=True) as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM auth_sessions WHERE agent_id = %s",
            (agent.id.value,),
        ).fetchone()
    return row["n"]


def test_hostile_origin_uses_the_common_error_envelope(monkeypatch):
    with TestClient(app) as client:
        _use_origins(monkeypatch, [_ALLOWED])
        agent = _seed_manager(client)
        response = _login(client, agent.email, origin=_HOSTILE)
    assert response.status_code == 403
    body = response.json()
    assert {"error", "error_code", "message"} <= set(body)
    assert body["error"] is True
    assert body["error_code"] == "FORBIDDEN"


def test_login_without_origin_succeeds(monkeypatch):
    with TestClient(app) as client:
        _use_origins(monkeypatch, [_ALLOWED])
        agent = _seed_manager(client)
        response = _login(client, agent.email)
    assert response.status_code == 200
    assert "leads_session" in response.cookies


def test_login_with_allowed_origin_succeeds_and_sets_cookie(monkeypatch):
    with TestClient(app) as client:
        _use_origins(monkeypatch, [_ALLOWED])
        agent = _seed_manager(client)
        response = _login(client, agent.email, origin=_ALLOWED)
    assert response.status_code == 200
    assert "leads_session" in response.cookies


def test_login_with_allowed_origin_and_port_succeeds(monkeypatch):
    with TestClient(app) as client:
        _use_origins(monkeypatch, ["http://localhost:8080"])
        agent = _seed_manager(client)
        response = _login(client, agent.email, origin="http://localhost:8080")
    assert response.status_code == 200


def test_login_with_hostile_origin_creates_no_session(monkeypatch):
    with TestClient(app) as client:
        _use_origins(monkeypatch, [_ALLOWED])
        agent = _seed_manager(client)
        before = _session_count(client, agent)
        response = _login(client, agent.email, origin=_HOSTILE)
        after = _session_count(client, agent)
    assert response.status_code == 403
    assert before == 0
    assert after == 0


def test_lookalike_domain_is_not_an_allowed_origin(monkeypatch):
    """Prefix matching would accept http://localhost:5173.evil.test as a
    suffix of the allowed origin; exact comparison must reject it."""
    with TestClient(app) as client:
        _use_origins(monkeypatch, [_ALLOWED])
        agent = _seed_manager(client)
        response = _login(client, agent.email, origin="http://localhost:5173.evil.test")
    assert response.status_code == 403


def test_non_browser_reads_without_origin_still_work(monkeypatch):
    with TestClient(app) as client:
        _use_origins(monkeypatch, [_ALLOWED])
        agent = _seed_manager(client)
        token = _login(client, agent.email).cookies["leads_session"]
        me = client.get("/api/v1/auth/me", headers={"Cookie": f"leads_session={token}"})
    assert me.status_code == 200


def test_hostile_origin_on_a_mutating_route_leaves_the_session_intact(monkeypatch):
    with TestClient(app) as client:
        _use_origins(monkeypatch, [_ALLOWED])
        agent = _seed_manager(client)
        token = _login(client, agent.email).cookies["leads_session"]
        headers = {"Cookie": f"leads_session={token}", "Origin": _HOSTILE}
        rejected = client.post(
            "/api/v1/rules/scoring",
            json={"name": "X", "conditions": [], "score_delta": 1},
            headers=headers,
        )
        still_valid = client.get(
            "/api/v1/auth/me", headers={"Cookie": f"leads_session={token}"}
        )
    assert rejected.status_code == 403
    assert still_valid.status_code == 200


def test_logout_with_hostile_origin_neither_revokes_nor_clears(monkeypatch):
    with TestClient(app) as client:
        _use_origins(monkeypatch, [_ALLOWED])
        agent = _seed_manager(client)
        token = _login(client, agent.email).cookies["leads_session"]
        headers = {"Cookie": f"leads_session={token}", "Origin": _HOSTILE}
        rejected = client.post("/api/v1/auth/logout", headers=headers)
        cleared = rejected.headers.get("set-cookie", "")
        still_valid = client.get(
            "/api/v1/auth/me", headers={"Cookie": f"leads_session={token}"}
        )
    assert rejected.status_code == 403
    assert "leads_session" not in cleared
    assert still_valid.status_code == 200


def test_preflight_with_allowed_origin_answers_credentials(monkeypatch):
    with TestClient(app) as client:
        _use_origins(monkeypatch, [_ALLOWED])
        response = client.options(
            "/api/v1/auth/login",
            headers={
                "Origin": _ALLOWED,
                "Access-Control-Request-Method": "POST",
            },
        )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == _ALLOWED
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_hostile_referer_without_origin_is_not_trusted(monkeypatch):
    """Referer, Host and X-Forwarded-* never substitute Origin: a hostile
    Referer travelling without Origin (a non-browser client) stays allowed."""
    with TestClient(app) as client:
        _use_origins(monkeypatch, [_ALLOWED])
        agent = _seed_manager(client)
        response = client.post(
            "/api/v1/auth/login",
            data={"username": agent.email, "password": _PASSWORD},
            headers={"Referer": "https://evil.test/"},
        )
    assert response.status_code == 200


def test_api_key_route_with_hostile_origin_is_rejected_before_auth(monkeypatch):
    """X-Api-Key routes cross the same middleware: a hostile Origin on a
    non-safe method is a 403 even with a garbage key, and no Bearer is
    introduced on that path to work around it."""
    with TestClient(app) as client:
        _use_origins(monkeypatch, [_ALLOWED])
        response = client.post(
            "/api/v1/rules/scoring",
            json={"name": "X", "conditions": [], "score_delta": 1},
            headers={"X-Api-Key": "not-a-real-key", "Origin": _HOSTILE},
        )
    assert response.status_code == 403
    assert "authorization" not in {k.lower() for k in response.request.headers}
