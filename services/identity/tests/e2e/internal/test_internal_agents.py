import uuid

from chassis.testing.contracts import assert_conforms, load_fixture

from domain.value_objects.agent_role import AgentRole
from tests import environment
from tests.e2e.seeds import seed_agent
from tests.e2e.tokens import FOREIGN_SIGNER, bearer, mint_service_token, mint_token


def _url(agent_id) -> str:
    return f"/internal/v1/agents/{agent_id}"


def test_lead_core_reads_an_agent_with_a_token_from_the_token_endpoint(direct):
    agent = seed_agent(direct, AgentRole.AGENT)
    token = direct.post("/internal/v1/service-tokens", json={
        "client_id": environment.SERVICE_CLIENT_ID, "client_secret": environment.SERVICE_CLIENT_SECRET,
        "audience": "identity",
    }).json()["access_token"]

    response = direct.get(_url(agent.id), headers=bearer(token))

    assert response.status_code == 200
    body = response.json()
    assert_conforms(body, "schemas/identity/agent.v1.schema.json")
    assert set(body) == set(load_fixture("identity/agent.v1.json"))
    assert body == {
        "agent_id": str(agent.id), "tenant_id": str(agent.tenant_id), "name": agent.name,
        "role": "AGENT", "is_active": True, "version": agent.version,
    }


def test_the_platform_admin_has_a_null_tenant(direct):
    admin = seed_agent(direct, AgentRole.ADMIN, None)

    body = direct.get(_url(admin.id), headers=bearer(mint_service_token())).json()

    assert_conforms(body, "schemas/identity/agent.v1.schema.json")
    assert body["tenant_id"] is None


def test_an_unknown_agent_is_not_found(direct):
    response = direct.get(_url(uuid.uuid4()), headers=bearer(mint_service_token()))

    assert (response.status_code, response.json()["error_code"]) == (404, "AGENT_NOT_FOUND")


def test_anything_but_a_lead_core_service_token_is_unauthorized(direct):
    agent = seed_agent(direct)
    attempts = [
        {},
        {"Authorization": "Basic abc"},
        bearer("not-a-jwt"),
        bearer(mint_token(agent.id, agent.tenant_id)),
        bearer(mint_service_token(caller="intake")),
        bearer(mint_service_token(audience="lead-core")),
        bearer(mint_service_token(ptype="human")),
        bearer(mint_service_token(signer=FOREIGN_SIGNER)),
    ]

    responses = [direct.get(_url(agent.id), headers=headers) for headers in attempts]

    assert [r.status_code for r in responses] == [401] * len(attempts)
    assert {r.json()["error_code"] for r in responses} == {"UNAUTHORIZED"}


def test_an_unauthenticated_caller_learns_nothing_about_the_path(direct):
    assert direct.get(_url("not-a-uuid")).status_code == 401
