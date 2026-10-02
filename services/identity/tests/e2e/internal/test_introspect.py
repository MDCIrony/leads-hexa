"""Contract of the identification endpoints the gateway calls (ADR-0032): who the
caller is, never what they may do. Same semantics as the backend's internal router."""
import uuid

from domain.value_objects.agent_role import AgentRole
from infrastructure.adapters.output.security.bcrypt_password_hasher import BcryptPasswordHasher
from tests.e2e.seeds import seed_agent, seed_tenant, session_headers, unit_of_work

_INTROSPECT = "/internal/v1/auth/introspect"
_SECRET = "integration-secret"
_HASHED = BcryptPasswordHasher().hash(_SECRET)


def _integration(client):
    """Seeded directly: POST /agents/integration-credential needs a Kafka broker
    the test environment deliberately does not have."""
    agent = seed_agent(client, AgentRole.INTEGRATION, hashed_password=_HASHED)
    return agent, f"{agent.id}.{_SECRET}"


def _claims(client, response):
    return client.app.state.container.token_verifier.verify(response.headers["X-Internal-Token"])


def test_valid_session_yields_a_human_token(direct):
    agent = seed_agent(direct)

    response = direct.get(_INTROSPECT, headers=session_headers(direct, agent))
    claims = _claims(direct, response)

    assert response.status_code == 200
    assert response.content == b""
    assert (claims.sub, claims.tid, claims.role, claims.ptype) == (
        str(agent.id), str(agent.tenant_id), "MANAGER", "human",
    )


def test_platform_admin_session_has_no_tenant_claim(direct):
    response = direct.get(_INTROSPECT, headers=session_headers(direct, seed_agent(direct, AgentRole.ADMIN, None)))

    assert response.status_code == 200
    assert _claims(direct, response).tid is None


def test_valid_api_key_yields_an_integration_token(direct):
    agent, api_key = _integration(direct)

    response = direct.get(_INTROSPECT, headers={"X-Api-Key": api_key})
    claims = _claims(direct, response)

    assert response.status_code == 200
    assert response.content == b""
    assert (claims.sub, claims.tid, claims.role, claims.ptype) == (
        str(agent.id), str(agent.tenant_id), "INTEGRATION", "integration",
    )


def test_invalid_or_malformed_api_key_is_unauthorized(direct):
    agent, _ = _integration(direct)

    wrong = direct.get(_INTROSPECT, headers={"X-Api-Key": f"{agent.id}.wrong"})
    malformed = direct.get(_INTROSPECT, headers={"X-Api-Key": "not-a-key"})

    assert (wrong.status_code, malformed.status_code) == (401, 401)
    assert wrong.json()["error"] is True
    assert "X-Internal-Token" not in wrong.headers


def test_api_key_wins_over_the_cookie(direct):
    headers = session_headers(direct, seed_agent(direct))
    agent, api_key = _integration(direct)

    valid_key = direct.get(_INTROSPECT, headers={**headers, "X-Api-Key": api_key})
    bad_key = direct.get(_INTROSPECT, headers={**headers, "X-Api-Key": f"{agent.id}.wrong"})

    assert _claims(direct, valid_key).ptype == "integration"
    assert bad_key.status_code == 401


def test_revoked_session_is_unauthorized(direct):
    headers = session_headers(direct, seed_agent(direct))
    assert direct.post("/api/v1/auth/logout", headers=headers).status_code == 204

    assert direct.get(_INTROSPECT, headers=headers).status_code == 401


def test_inactive_agent_session_is_unauthorized(direct):
    agent = seed_agent(direct)
    headers = session_headers(direct, agent)
    with unit_of_work(direct) as uow:
        agent.is_active = False
        uow.agents.save(agent)

    assert direct.get(_INTROSPECT, headers=headers).status_code == 401


def test_credentials_of_a_suspended_organization_are_unauthorized(direct):
    tenant = seed_tenant(direct, is_active=False)
    session = session_headers(direct, seed_agent(direct, tenant_id=tenant.id.value))
    key_agent = seed_agent(direct, AgentRole.INTEGRATION, tenant_id=tenant.id.value, hashed_password=_HASHED)

    by_session = direct.get(_INTROSPECT, headers=session)
    by_key = direct.get(_INTROSPECT, headers={"X-Api-Key": f"{key_agent.id}.{_SECRET}"})

    assert (by_session.status_code, by_key.status_code) == (401, 401)


def test_no_credential_is_unauthorized_unless_optional(direct):
    required = direct.get(_INTROSPECT)
    optional = direct.get(f"{_INTROSPECT}?optional=true")

    assert required.status_code == 401
    assert required.json()["message"] == "Authentication required"
    assert optional.status_code == 204
    assert "X-Internal-Token" not in optional.headers


def test_optional_never_downgrades_an_invalid_credential_to_anonymous(direct):
    headers = session_headers(direct, seed_agent(direct))
    direct.post("/api/v1/auth/logout", headers=headers)

    revoked = direct.get(f"{_INTROSPECT}?optional=true", headers=headers)
    bad_key = direct.get(f"{_INTROSPECT}?optional=true", headers={"X-Api-Key": f"{uuid.uuid4()}.x"})

    assert (revoked.status_code, bad_key.status_code) == (401, 401)


def test_jwks_publishes_public_keys_only(direct):
    response = direct.get("/internal/v1/jwks")

    keys = response.json()["keys"]
    assert response.status_code == 200
    assert keys and all(key["kty"] == "OKP" and "d" not in key for key in keys)
    assert set(keys[0]) == {"kty", "crv", "x", "kid", "alg", "use"}


def test_internal_routes_stay_out_of_the_public_schema(direct):
    assert "/internal/" not in direct.get("/openapi.json").text
