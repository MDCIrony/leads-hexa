"""Every agent write records its AgentState on the internal channel, in the same unit of work."""
import uuid

import pytest

from application.dtos.agents import (
    CreateAgentCommand,
    GetAgentQuery,
    IssueIntegrationCredentialCommand,
    UpdateAgentCommand,
)
from application.use_cases.agents.commands import CreateAgentUseCase, DeactivateAgentUseCase, UpdateAgentUseCase
from application.use_cases.agents.integration_credential import IssueIntegrationCredentialUseCase
from domain.agents.agent import Agent
from domain.exceptions import DomainException
from domain.tenants.tenant import Tenant
from tests.unit.application.doubles.services import FakeMessagingCredentialProvisioner, FakePasswordHasher
from tests.unit.application.doubles.uow import InMemoryUnitOfWork


def _agent_states(uow: InMemoryUnitOfWork) -> list[dict]:
    events = uow.events()
    assert {(e.event_type, e.channel) for e in events} <= {("AgentState", "internal")}
    assert all(e.partition_key == e.payload["agent_id"] for e in events)
    return [e.payload for e in events]


def test_creating_records_the_new_agent():
    uow = InMemoryUnitOfWork()
    saved = CreateAgentUseCase(uow=uow, password_hasher=FakePasswordHasher()).execute(CreateAgentCommand(
        name="Jane", email="jane@test.com", password="plain-password", role="AGENT", tenant_id=uuid.uuid4(),
    ))

    states = _agent_states(uow)
    assert [s["agent_id"] for s in states] == [str(saved.id)]
    assert states[0]["version"] == 1
    assert "email" not in states[0] and "hashed_password" not in states[0]


def test_a_rejected_creation_records_nothing():
    uow = InMemoryUnitOfWork()
    use_case = CreateAgentUseCase(uow=uow, password_hasher=FakePasswordHasher())
    use_case.execute(CreateAgentCommand(name="Jane", email="jane@test.com", password="x"))
    with pytest.raises(DomainException):
        use_case.execute(CreateAgentCommand(name="Jane", email="jane@test.com", password="x"))
    assert len(_agent_states(uow)) == 1


def test_deactivating_records_an_inactive_state_with_a_higher_version():
    uow = InMemoryUnitOfWork()
    tenant = uuid.uuid4()
    agent = uow.agents.save(Agent.create("Ana", "ana@acme.test", tenant_id=tenant))
    before = agent.version

    DeactivateAgentUseCase(uow=uow, messaging_provisioner=FakeMessagingCredentialProvisioner()).execute(
        GetAgentQuery(tenant_id=tenant, agent_id=agent.id.value)
    )

    states = _agent_states(uow)
    assert len(states) == 1
    assert states[0]["is_active"] is False
    assert states[0]["version"] > before


def test_updating_records_the_new_state():
    uow = InMemoryUnitOfWork()
    tenant = uuid.uuid4()
    agent = uow.agents.save(Agent.create("Ana", "ana@acme.test", tenant_id=tenant))

    UpdateAgentUseCase(uow=uow).execute(UpdateAgentCommand(tenant_id=tenant, agent_id=agent.id.value, name="Ana María"))

    assert [(s["name"], s["version"]) for s in _agent_states(uow)] == [("Ana María", 2)]


def test_issuing_and_rotating_an_integration_credential_record_each_write():
    uow = InMemoryUnitOfWork()
    tenant = uow.tenants.save(Tenant.create(name="Acme"))
    use_case = IssueIntegrationCredentialUseCase(
        uow=uow, password_hasher=FakePasswordHasher(), messaging_provisioner=FakeMessagingCredentialProvisioner(),
    )

    use_case.execute(IssueIntegrationCredentialCommand(tenant_id=tenant.id.value))
    use_case.execute(IssueIntegrationCredentialCommand(tenant_id=tenant.id.value))

    assert [(s["role"], s["version"]) for s in _agent_states(uow)] == [("INTEGRATION", 1), ("INTEGRATION", 2)]
