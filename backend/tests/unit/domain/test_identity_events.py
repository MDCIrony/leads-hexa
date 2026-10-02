import uuid

from domain.entities.agent import Agent
from domain.entities.tenant import Tenant
from domain.events.identity_events import AgentState, TenantState
from domain.value_objects.enums import AgentRole


def test_agent_state_carries_exactly_the_public_identity():
    tenant_id = uuid.uuid4()
    agent = Agent.create(
        "Ana", "ana@acme.test", role=AgentRole.MANAGER, hashed_password="hash",
        group_id=uuid.uuid4(), tenant_id=tenant_id, version=4,
    )

    event = AgentState.of(agent)

    # No email, hash or group: identity is not where those live downstream.
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
