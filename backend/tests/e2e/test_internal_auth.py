"""Contract of the identification endpoints the gateway calls (ADR-0032):
who the caller is, never what they may do."""
import uuid

from fastapi.testclient import TestClient

from auth_helpers import session_headers
from domain.entities.agent import Agent
from domain.value_objects.enums import AgentRole
from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
from infrastructure.adapters.output.security.bcrypt_password_hasher import BcryptPasswordHasher
from infrastructure.main import app

_INTROSPECT = "/internal/v1/auth/introspect"
_SECRET = "integration-secret"
_HASHED = BcryptPasswordHasher().hash(_SECRET)


def _seed(client, role=AgentRole.MANAGER, tenant_id=None, hashed_password=None) -> Agent:
    agent = Agent.create(
        name="Internal", email=f"int_{uuid.uuid4().hex[:8]}@test.com", role=role,
        hashed_password=hashed_password, tenant_id=tenant_id,
    )
    with PostgresUnitOfWork(client.app.state.container.database) as uow:
        uow.agents.save(agent)
    return agent


def _integration(client):
    """Seeded directly: POST /agents/integration-credential needs a Kafka broker
    the test environment deliberately does not have."""
    agent = _seed(client, AgentRole.INTEGRATION, uuid.uuid4(), _HASHED)
    return agent, f"{agent.id}.{_SECRET}"


def _claims(client, response):
    return client.app.state.container.token_verifier.verify(response.headers["X-Internal-Token"])


def test_valid_session_yields_a_human_token():
    with TestClient(app) as client:
        agent = _seed(client, tenant_id=uuid.uuid4())

        response = client.get(_INTROSPECT, headers=session_headers(agent))
        claims = _claims(client, response)

    assert response.status_code == 200
    assert response.content == b""
    assert (claims.sub, claims.tid, claims.role, claims.ptype) == (
        str(agent.id), str(agent.tenant_id), "MANAGER", "human",
    )


def test_platform_admin_session_has_no_tenant_claim():
    with TestClient(app) as client:
        agent = _seed(client, AgentRole.ADMIN)

        response = client.get(_INTROSPECT, headers=session_headers(agent))

    assert response.status_code == 200
    assert _claims(client, response).tid is None


def test_valid_api_key_yields_an_integration_token():
    with TestClient(app) as client:
        agent, api_key = _integration(client)

        response = client.get(_INTROSPECT, headers={"X-Api-Key": api_key})
        claims = _claims(client, response)

    assert response.status_code == 200
    assert response.content == b""
    assert (claims.sub, claims.tid, claims.role, claims.ptype) == (
        str(agent.id), str(agent.tenant_id), "INTEGRATION", "integration",
    )


def test_invalid_api_key_is_unauthorized():
    with TestClient(app) as client:
        agent, _ = _integration(client)

        response = client.get(_INTROSPECT, headers={"X-Api-Key": f"{agent.id}.wrong"})

    assert response.status_code == 401
    assert response.json()["error"] is True
    assert "X-Internal-Token" not in response.headers


def test_api_key_wins_over_the_cookie():
    with TestClient(app) as client:
        manager = _seed(client, tenant_id=uuid.uuid4())
        agent, api_key = _integration(client)

        valid_key = client.get(_INTROSPECT, headers={**session_headers(manager), "X-Api-Key": api_key})
        bad_key = client.get(
            _INTROSPECT, headers={**session_headers(manager), "X-Api-Key": f"{agent.id}.wrong"},
        )

    assert _claims(client, valid_key).ptype == "integration"
    assert bad_key.status_code == 401


def test_revoked_session_is_unauthorized():
    with TestClient(app) as client:
        headers = session_headers(_seed(client, tenant_id=uuid.uuid4()))
        assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204

        response = client.get(_INTROSPECT, headers=headers)

    assert response.status_code == 401


def test_inactive_agent_session_is_unauthorized():
    with TestClient(app) as client:
        agent = _seed(client, tenant_id=uuid.uuid4())
        headers = session_headers(agent)
        agent.is_active = False
        with PostgresUnitOfWork(client.app.state.container.database) as uow:
            uow.agents.save(agent)

        response = client.get(_INTROSPECT, headers=headers)

    assert response.status_code == 401


def test_no_credential_is_unauthorized_unless_optional():
    with TestClient(app) as client:
        required = client.get(_INTROSPECT)
        optional = client.get(f"{_INTROSPECT}?optional=true")

    assert required.status_code == 401
    assert required.json()["message"] == "Authentication required"
    assert optional.status_code == 204
    assert "X-Internal-Token" not in optional.headers


def test_optional_never_downgrades_an_invalid_credential_to_anonymous():
    with TestClient(app) as client:
        headers = session_headers(_seed(client, tenant_id=uuid.uuid4()))
        client.post("/api/v1/auth/logout", headers=headers)

        revoked = client.get(f"{_INTROSPECT}?optional=true", headers=headers)
        bad_key = client.get(f"{_INTROSPECT}?optional=true", headers={"X-Api-Key": f"{uuid.uuid4()}.x"})

    assert revoked.status_code == 401
    assert bad_key.status_code == 401


def test_jwks_publishes_public_keys_only():
    with TestClient(app) as client:
        response = client.get("/internal/v1/jwks")

    keys = response.json()["keys"]
    assert response.status_code == 200
    assert keys and all(key["kty"] == "OKP" and "d" not in key for key in keys)


def test_internal_routes_stay_out_of_the_public_schema():
    with TestClient(app) as client:
        schema = client.get("/openapi.json").text

    assert "/internal/" not in schema
