import uuid

import pytest

from application.dtos.agents import CreateAgentCommand, GetAgentQuery, GetAgentsQuery, UpdateAgentCommand
from application.use_cases.agents.commands import CreateAgentUseCase, DeactivateAgentUseCase, UpdateAgentUseCase
from application.use_cases.agents.queries import GetAgentStateUseCase, GetAgentsUseCase, GetAgentUseCase
from domain.agents.agent import Agent
from domain.exceptions import AgentNotFoundException, DomainException
from domain.policies.authorization_policy import AuthorizationPolicy
from domain.value_objects.agent_role import AgentRole
from tests.unit.application.doubles.services import FakeMessagingCredentialProvisioner, FakePasswordHasher
from tests.unit.application.doubles.uow import InMemoryUnitOfWork


def _create(uow, **overrides):
    fields = {"name": "Ana", "email": "ana@acme.test", "password": "x", "tenant_id": uuid.uuid4(), **overrides}
    return CreateAgentUseCase(uow=uow, password_hasher=FakePasswordHasher()).execute(CreateAgentCommand(**fields))


def _deactivate(uow, tenant_id, agent_id, provisioner=None):
    return DeactivateAgentUseCase(uow=uow, messaging_provisioner=provisioner or FakeMessagingCredentialProvisioner()).execute(
        GetAgentQuery(tenant_id=tenant_id, agent_id=agent_id)
    )


def test_get_agent_raises_when_missing():
    with pytest.raises(AgentNotFoundException) as exc_info:
        GetAgentUseCase(uow=InMemoryUnitOfWork()).execute(GetAgentQuery(tenant_id=uuid.uuid4(), agent_id=uuid.uuid4()))
    assert exc_info.value.error_code == "AGENT_NOT_FOUND"


def test_get_agent_of_another_organization_reads_as_missing():
    uow = InMemoryUnitOfWork()
    agent = _create(uow)
    with pytest.raises(AgentNotFoundException):
        GetAgentUseCase(uow=uow).execute(GetAgentQuery(tenant_id=uuid.uuid4(), agent_id=agent.id.value))


def test_listing_counts_the_same_population_it_lists():
    uow = InMemoryUnitOfWork()
    tenant = uuid.uuid4()
    for index in range(3):
        _create(uow, email=f"a{index}@acme.test", tenant_id=tenant)
    gone = _create(uow, email="gone@acme.test", tenant_id=tenant, is_active=False)
    _create(uow, email="other@else.test")

    active = GetAgentsUseCase(uow=uow).execute(GetAgentsQuery(tenant_id=tenant, limit=2))
    inactive = GetAgentsUseCase(uow=uow).execute(GetAgentsQuery(tenant_id=tenant, is_active=False))
    both = GetAgentsUseCase(uow=uow).execute(GetAgentsQuery(tenant_id=tenant, is_active=None))

    assert (len(active.items), active.total) == (2, 3)
    assert [a.id for a in inactive.items] == [gone.id] and inactive.total == 1
    assert both.total == 4


def test_create_agent_hashes_the_password_and_stores_role_and_tenant():
    tenant = uuid.UUID("11111111-1111-1111-1111-111111111111")
    saved = _create(InMemoryUnitOfWork(), password="plain-password", role="MANAGER", tenant_id=tenant)
    assert saved.role == AgentRole.MANAGER
    assert str(saved.tenant_id) == str(tenant)
    assert saved.hashed_password == "hashed:plain-password"


def test_create_agent_defaults_role_to_agent_and_tenant_to_none():
    saved = CreateAgentUseCase(uow=InMemoryUnitOfWork(), password_hasher=FakePasswordHasher()).execute(
        CreateAgentCommand(name="Bob", email="bob@test.com", password="x")
    )
    assert saved.role == AgentRole.AGENT
    assert saved.tenant_id is None


def test_create_agent_normalizes_email_and_rejects_its_normalized_duplicate():
    uow = InMemoryUnitOfWork()
    saved = _create(uow, email="  Jane@Example.Test ")
    assert saved.email == "jane@example.test"
    with pytest.raises(DomainException) as exc_info:
        _create(uow, name="Other", email="JANE@example.test")
    assert exc_info.value.error_code == "EMAIL_ALREADY_EXISTS"


def test_update_renames_and_reactivates_within_the_organization():
    uow = InMemoryUnitOfWork()
    tenant = uuid.uuid4()
    agent = _create(uow, tenant_id=tenant, is_active=False)

    updated = UpdateAgentUseCase(uow=uow).execute(
        UpdateAgentCommand(tenant_id=tenant, agent_id=agent.id.value, name="Ana María", is_active=True)
    )

    assert (updated.name, updated.is_active) == ("Ana María", True)


def test_update_of_an_agent_of_another_organization_reads_as_missing():
    uow = InMemoryUnitOfWork()
    agent = _create(uow)
    with pytest.raises(AgentNotFoundException):
        UpdateAgentUseCase(uow=uow).execute(UpdateAgentCommand(tenant_id=uuid.uuid4(), agent_id=agent.id.value, name="X"))


class TestDeactivateAgent:
    def test_deactivating_keeps_the_record(self):
        uow = InMemoryUnitOfWork()
        tenant = uuid.uuid4()
        agent = _create(uow, tenant_id=tenant)

        _deactivate(uow, tenant, agent.id.value)

        # The record itself survives: an agent's history must stay readable.
        survivor = uow.agents.get_by_id(agent.id.value)
        assert survivor is not None and survivor.is_active is False
        assert uow.agents.count_by_tenant(tenant) == 0

    def test_deactivating_a_regular_agent_does_not_touch_the_broker(self):
        uow = InMemoryUnitOfWork()
        tenant = uuid.uuid4()
        agent = _create(uow, tenant_id=tenant)
        provisioner = FakeMessagingCredentialProvisioner()

        _deactivate(uow, tenant, agent.id.value, provisioner)

        assert provisioner.revoked == []

    def test_deactivating_an_integration_credential_revokes_its_kafka_credential(self):
        uow = InMemoryUnitOfWork()
        tenant = uuid.uuid4()
        agent = uow.agents.save(Agent.create("Integración", "integration@acme.invalid", role=AgentRole.INTEGRATION, tenant_id=tenant))
        provisioner = FakeMessagingCredentialProvisioner()

        _deactivate(uow, tenant, agent.id.value, provisioner)

        assert provisioner.revoked == [tenant]

    def test_a_failed_revoke_does_not_undo_the_deactivation(self):
        uow = InMemoryUnitOfWork()
        tenant = uuid.uuid4()
        agent = uow.agents.save(Agent.create("Integración", "integration@acme.invalid", role=AgentRole.INTEGRATION, tenant_id=tenant))

        saved = _deactivate(uow, tenant, agent.id.value, FakeMessagingCredentialProvisioner(fail=True))

        assert saved.is_active is False
        assert [e.payload["is_active"] for e in uow.events("AgentState")] == [False]


class TestGetAgentState:
    def test_returns_the_snapshot_of_any_agent_including_inactive_ones(self):
        uow = InMemoryUnitOfWork()
        agent = _create(uow, is_active=False)

        state = GetAgentStateUseCase(uow).execute(agent.id.value)

        assert state.as_payload() == {
            "agent_id": str(agent.id), "tenant_id": str(agent.tenant_id), "name": "Ana",
            "role": "AGENT", "is_active": False, "version": 1,
        }

    def test_an_unknown_agent_is_agent_not_found(self):
        with pytest.raises(AgentNotFoundException) as exc_info:
            GetAgentStateUseCase(InMemoryUnitOfWork()).execute(uuid.uuid4())
        assert exc_info.value.error_code == "AGENT_NOT_FOUND"


def test_authorization_policy_rejects_integration_the_same_way_it_rejects_admin():
    manager = Agent.create("M", "m@acme.test", role=AgentRole.MANAGER, tenant_id=uuid.uuid4())
    assert AuthorizationPolicy.can_create_agent_with_role(manager, AgentRole.INTEGRATION) is False
