import uuid

from domain.agents.agent import Agent
from domain.events.identity_events import AgentState, TenantState
from domain.tenants.tenant import Tenant
from domain.value_objects.agent_role import AgentRole

# The payload keys contracts/events/AgentState.v1.schema.json requires. Copied
# here because a domain test reads no files; A4's conformance test checks the
# full envelope against the schema itself.
_AGENT_STATE_CONTRACT_KEYS = {"agent_id", "tenant_id", "name", "role", "is_active", "version"}


def test_agent_state_payload_has_exactly_the_contract_keys():
    agent = Agent.create("Ana", "ana@acme.test", tenant_id=uuid.uuid4())

    assert set(AgentState.of(agent).as_payload()) == _AGENT_STATE_CONTRACT_KEYS


def test_agent_state_carries_exactly_the_public_identity():
    tenant_id = uuid.uuid4()
    agent = Agent.create(
        "Ana", "ana@acme.test", role=AgentRole.MANAGER, hashed_password="hash",
        tenant_id=tenant_id, version=4,
    )

    event = AgentState.of(agent)

    # No email or hash: identity is not where those live downstream.
    assert event.as_payload() == {
        "agent_id": str(agent.id),
        "tenant_id": str(tenant_id),
        "name": "Ana",
        "role": "MANAGER",
        "is_active": True,
        "version": 4,
    }
    assert event.partition_key == str(agent.id)
    assert event.tenant_id == str(tenant_id)
    assert event.event_type == "AgentState"


def test_a_platform_admin_has_no_tenant():
    event = AgentState.of(Agent.create("Root", "root@x.test", role=AgentRole.ADMIN))

    assert event.tenant_id is None
    assert event.as_payload()["tenant_id"] is None


def test_tenant_state_carries_name_slug_status_and_version():
    tenant = Tenant.create(name="Acme Corp", version=2)
    tenant.deactivate()

    event = TenantState.of(tenant)

    assert event.as_payload() == {
        "tenant_id": str(tenant.id.value),
        "name": "Acme Corp",
        "slug": "acme-corp",
        "is_active": False,
        "version": 2,
    }
    assert event.partition_key == str(tenant.id.value)
    assert event.tenant_id == str(tenant.id.value)


def test_the_envelope_fields_stay_out_of_the_payload():
    # event_id and occurred_on travel in the envelope; repeating them would let the two disagree.
    event = TenantState.of(Tenant.create(name="Acme"))

    assert event.event_id is not None and event.occurred_on is not None
    assert {"event_id", "occurred_on"}.isdisjoint(event.as_payload())
