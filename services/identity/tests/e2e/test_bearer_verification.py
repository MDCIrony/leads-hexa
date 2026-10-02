"""How identity's own bearer routes treat the token the gateway forwards: the same
rules as every other service (chassis.auth), over keys read from memory."""
import uuid

from chassis.auth import AUDIENCE, ISSUER, JwksCache, TokenVerifier

from tests.e2e.seeds import bootstrap_admin, create_organization, unit_of_work
from tests.e2e.tokens import FOREIGN_SIGNER, bearer, mint_token


def _manager_token(client) -> str:
    """A bearer for the real manager of a real organization, as introspection would mint it."""
    tenant, _ = create_organization(client, bootstrap_admin(client))
    with unit_of_work(client) as uow:
        manager = uow.agents.get_by_id(uuid.UUID(tenant["manager"]["id"]))
    return mint_token(manager.id, manager.tenant_id, role="MANAGER")


def test_a_signed_bearer_is_all_a_bearer_route_needs(client, direct):
    response = direct.get("/api/v1/agents", headers=bearer(_manager_token(client)))

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_bad_bearers_are_unauthorized(direct):
    attempts = [
        {},
        {"Authorization": "Basic abc"},
        bearer("not-a-jwt"),
        bearer(mint_token(tenant_id=uuid.uuid4(), signer=FOREIGN_SIGNER)),
        bearer(mint_token(tenant_id=uuid.uuid4(), role="NOT_A_ROLE")),
        bearer(mint_token(tenant_id=uuid.uuid4(), role="INTEGRATION", ptype="integration")),
    ]

    responses = [direct.get("/api/v1/agents", headers=headers) for headers in attempts]

    assert [r.status_code for r in responses] == [401] * len(attempts)
    assert {r.json()["error_code"] for r in responses} == {"UNAUTHORIZED"}


def test_unavailable_signing_keys_are_a_503_not_a_401(direct, monkeypatch):
    def unreachable() -> dict:
        raise ConnectionError("keys are gone")

    container = direct.app.state.container
    monkeypatch.setattr(
        container, "token_verifier", TokenVerifier(JwksCache(unreachable), issuer=ISSUER, audience=AUDIENCE),
    )

    response = direct.get("/api/v1/agents", headers=bearer(mint_token(tenant_id=uuid.uuid4())))

    assert (response.status_code, response.json()["error_code"]) == (503, "SERVICE_UNAVAILABLE")
