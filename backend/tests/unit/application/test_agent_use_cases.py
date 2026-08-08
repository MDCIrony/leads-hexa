import uuid
import pytest
from application.dtos.queries import GetAgentQuery
from application.dtos.commands import CreateAgentCommand, UpdateAgentCommand
from application.use_cases.agent_use_cases import (
    CreateAgentUseCase,
    DeactivateAgentUseCase,
    GetAgentUseCase,
    UpdateAgentUseCase,
)
from domain.entities.sales_group import SalesGroup
from domain.value_objects.enums import AgentRole
from domain.exceptions import AgentNotFoundException, DomainException
from tests.unit.mocks.fake_password_hasher import FakePasswordHasher
from tests.unit.mocks.in_memory_agent_repo import InMemoryAgentRepository
from tests.unit.mocks.in_memory_uow import InMemoryUnitOfWork
from tests.unit.mocks.in_memory_lead_repo import InMemoryLeadRepository
from tests.unit.mocks.in_memory_rule_repo import InMemoryRuleRepository
from tests.unit.mocks.in_memory_sales_group_repo import InMemorySalesGroupRepository


def _uow() -> InMemoryUnitOfWork:
    return InMemoryUnitOfWork(
        InMemoryLeadRepository(),
        InMemoryRuleRepository(),
        InMemoryAgentRepository(),
        groups=InMemorySalesGroupRepository(),
    )


def test_get_agent_use_case_raises_when_agent_missing():
    uow = _uow()
    use_case = GetAgentUseCase(uow=uow)

    with pytest.raises(AgentNotFoundException) as exc_info:
        use_case.execute(GetAgentQuery(tenant_id=uuid.uuid4(), agent_id=uuid.uuid4()))

    assert exc_info.value.error_code == "AGENT_NOT_FOUND"


def test_create_agent_hashes_the_password_and_stores_role_and_tenant():
    uow = _uow()
    use_case = CreateAgentUseCase(uow=uow, password_hasher=FakePasswordHasher())
    command = CreateAgentCommand(
        name="Jane",
        email="jane@test.com",
        password="plain-password",
        role="MANAGER",
        tenant_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
    )
    saved = use_case.execute(command)
    assert saved.role == AgentRole.MANAGER
    assert str(saved.tenant_id) == "11111111-1111-1111-1111-111111111111"
    assert saved.hashed_password == "hashed:plain-password"


def test_create_agent_defaults_role_to_agent_and_tenant_to_none():
    uow = _uow()
    use_case = CreateAgentUseCase(uow=uow, password_hasher=FakePasswordHasher())
    command = CreateAgentCommand(name="Bob", email="bob@test.com", password="x")
    saved = use_case.execute(command)
    assert saved.role == AgentRole.AGENT
    assert saved.tenant_id is None


class TestUpdateAgent:
    def test_moves_an_agent_to_another_group_of_the_same_organization(self):
        uow = _uow()
        tenant = uuid.uuid4()
        origin = uow.groups.save(SalesGroup.create(tenant_id=tenant, name="Norte"))
        destination = uow.groups.save(SalesGroup.create(tenant_id=tenant, name="Sur"))
        agent = CreateAgentUseCase(uow=uow, password_hasher=FakePasswordHasher()).execute(
            CreateAgentCommand(
                name="Ana",
                email="ana@acme.test",
                password="x",
                group_id=origin.id.value,
                tenant_id=tenant,
            )
        )

        updated = UpdateAgentUseCase(uow=uow).execute(
            UpdateAgentCommand(
                tenant_id=tenant, agent_id=agent.id.value, group_id=destination.id.value
            )
        )

        assert updated.group_id.value == destination.id.value

    def test_moving_an_agent_to_a_group_of_another_organization_is_rejected(self):
        uow = _uow()
        tenant, other_tenant = uuid.uuid4(), uuid.uuid4()
        foreign_group = uow.groups.save(SalesGroup.create(tenant_id=other_tenant, name="Ajeno"))
        agent = CreateAgentUseCase(uow=uow, password_hasher=FakePasswordHasher()).execute(
            CreateAgentCommand(name="Ana", email="ana@acme.test", password="x", tenant_id=tenant)
        )

        with pytest.raises(DomainException) as exc:
            UpdateAgentUseCase(uow=uow).execute(
                UpdateAgentCommand(
                    tenant_id=tenant, agent_id=agent.id.value, group_id=foreign_group.id.value
                )
            )
        assert exc.value.error_code == "GROUP_NOT_FOUND"


class TestDeactivateAgent:
    def test_deactivating_excludes_the_agent_from_candidates_without_erasing_it(self):
        uow = _uow()
        tenant = uuid.uuid4()
        agent = CreateAgentUseCase(uow=uow, password_hasher=FakePasswordHasher()).execute(
            CreateAgentCommand(name="Ana", email="ana@acme.test", password="x", tenant_id=tenant)
        )

        DeactivateAgentUseCase(uow=uow).execute(
            GetAgentQuery(tenant_id=tenant, agent_id=agent.id.value)
        )

        assert agent.id.value not in {a.id.value for a in uow.agents.get_available_agents(tenant)}
        # The record itself survives: an agent's history must stay readable.
        survivor = uow.agents.get_by_id(agent.id.value)
        assert survivor is not None
        assert survivor.is_active is False
