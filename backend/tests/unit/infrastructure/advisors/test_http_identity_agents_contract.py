"""HttpIdentityAgents against identity's internal contract: the fixtures of
contracts/ served by an httpx.MockTransport, so a contract change breaks here."""
import json
import uuid

import httpx
import pytest
from chassis.auth import ServiceTokenClient
from chassis.testing.contracts import assert_conforms, load_fixture

from domain.exceptions import DomainException
from domain.value_objects.enums import AgentRole
from infrastructure.adapters.output.http.advisors.http_identity_agents import HttpIdentityAgents

_IDENTITY = "http://identity:8000"
_AGENT = load_fixture("identity/agent.v1.json")
_TOKEN = load_fixture("identity/service-token.v1.json")


class _Identity:
    def __init__(self, agent_status=200, agent_body=None, token_status=200, fail=False) -> None:
        self.agent_status, self.agent_body = agent_status, agent_body or _AGENT
        self.token_status, self.fail = token_status, fail
        self.token_requests: list[dict] = []
        self.agent_requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if self.fail:
            raise httpx.ConnectError("refused", request=request)
        if request.url.path == "/internal/v1/service-tokens":
            self.token_requests.append(json.loads(request.content))
            return httpx.Response(self.token_status, json=_TOKEN)
        self.agent_requests.append(request)
        return httpx.Response(self.agent_status, json=self.agent_body)


def _adapter(identity: _Identity) -> HttpIdentityAgents:
    client = httpx.Client(transport=httpx.MockTransport(identity))
    tokens = ServiceTokenClient(f"{_IDENTITY}/internal/v1/service-tokens", "lead-core", "secret", "identity",
                                post=client.post)
    return HttpIdentityAgents(_IDENTITY, tokens, client)


def test_the_fixtures_conform_to_identity_schemas():
    assert_conforms(_AGENT, "schemas/identity/agent.v1.schema.json")
    assert_conforms(_TOKEN, "schemas/identity/service-token.v1.schema.json")


def test_an_agent_is_fetched_with_a_service_token_for_identity():
    identity = _Identity()

    advisor = _adapter(identity).fetch(uuid.UUID(_AGENT["agent_id"]))

    assert identity.token_requests == [{"client_id": "lead-core", "client_secret": "secret", "audience": "identity"}]
    request = identity.agent_requests[0]
    assert request.method == "GET"
    assert request.url.path == f"/internal/v1/agents/{_AGENT['agent_id']}"
    assert request.headers["Authorization"] == f"Bearer {_TOKEN['access_token']}"
    assert (str(advisor.agent_id), str(advisor.tenant_id), advisor.name, advisor.role, advisor.is_active,
            advisor.version) == (_AGENT["agent_id"], _AGENT["tenant_id"], _AGENT["name"], AgentRole.AGENT,
                                 _AGENT["is_active"], _AGENT["version"])
    assert advisor.group_id is None


def test_the_token_is_reused_across_fetches():
    identity = _Identity()
    adapter = _adapter(identity)

    adapter.fetch(uuid.uuid4())
    adapter.fetch(uuid.uuid4())

    assert len(identity.token_requests) == 1


def test_an_unknown_agent_is_none():
    assert _adapter(_Identity(agent_status=404, agent_body={
        "error": True, "error_code": "AGENT_NOT_FOUND", "message": "x"})).fetch(uuid.uuid4()) is None


def test_the_platform_admin_has_no_organization_to_advise_in():
    admin = {**_AGENT, "tenant_id": None, "role": "ADMIN"}
    assert_conforms(admin, "schemas/identity/agent.v1.schema.json")
    assert _adapter(_Identity(agent_body=admin)).fetch(uuid.uuid4()) is None


@pytest.mark.parametrize("identity", [
    _Identity(fail=True),
    _Identity(token_status=401),
    _Identity(agent_status=401),
    _Identity(agent_status=500),
    _Identity(agent_body={"agent_id": "not-a-uuid"}),
], ids=["unreachable", "token-refused", "agent-call-refused", "server-error", "malformed-body"])
def test_anything_but_an_answer_is_service_unavailable(identity):
    with pytest.raises(DomainException) as exc:
        _adapter(identity).fetch(uuid.uuid4())
    assert exc.value.error_code == "SERVICE_UNAVAILABLE"


def test_a_refused_token_is_dropped_so_the_next_call_fetches_another():
    identity = _Identity(agent_status=401, agent_body={
        "error": True, "error_code": "UNAUTHORIZED", "message": "Authentication required"})
    adapter = _adapter(identity)

    for _ in range(2):
        with pytest.raises(DomainException):
            adapter.fetch(uuid.uuid4())

    assert len(identity.token_requests) == 2


def test_the_lookup_carries_the_callers_request_id():
    from chassis.web import request_id_var

    identity = _Identity()
    reset = request_id_var.set("req-123")
    try:
        _adapter(identity).fetch(uuid.UUID(_AGENT["agent_id"]))
    finally:
        request_id_var.reset(reset)

    assert identity.agent_requests[0].headers["X-Request-Id"] == "req-123"
