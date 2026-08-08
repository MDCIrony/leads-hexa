import uuid
import pytest
from application.dtos.queries import GetAgentQuery
from application.dtos.commands import CreateAgentCommand
from application.use_cases.agent_use_cases import GetAgentUseCase, CreateAgentUseCase
from domain.value_objects.enums import AgentRole
from domain.exceptions import AgentNotFoundException
from tests.unit.mocks.fake_password_hasher import FakePasswordHasher
from tests.unit.mocks.in_memory_agent_repo import InMemoryAgentRepository
from tests.unit.mocks.in_memory_uow import InMemoryUnitOfWork
from tests.unit.mocks.in_memory_lead_repo import InMemoryLeadRepository
from tests.unit.mocks.in_memory_rule_repo import InMemoryRuleRepository


def test_get_agent_use_case_raises_when_agent_missing():
    uow = InMemoryUnitOfWork(
        InMemoryLeadRepository(), InMemoryRuleRepository(), InMemoryAgentRepository()
    )
    use_case = GetAgentUseCase(uow=uow)

    with pytest.raises(AgentNotFoundException) as exc_info:
        use_case.execute(GetAgentQuery(tenant_id=uuid.uuid4(), agent_id=uuid.uuid4()))

    assert exc_info.value.error_code == "AGENT_NOT_FOUND"


def test_create_agent_hashes_the_password_and_stores_role_and_tenant():
    uow = InMemoryUnitOfWork(agents=InMemoryAgentRepository())
    use_case = CreateAgentUseCase(uow=uow, password_hasher=FakePasswordHasher())
    command = CreateAgentCommand(
        name="Jane",
        email="jane@test.com",
        team="Sales",
        password="plain-password",
        role="MANAGER",
        tenant_id="11111111-1111-1111-1111-111111111111",
    )
    saved = use_case.execute(command)
    assert saved.role == AgentRole.MANAGER
    assert str(saved.tenant_id) == "11111111-1111-1111-1111-111111111111"
    assert saved.hashed_password == "hashed:plain-password"


def test_create_agent_defaults_role_to_agent_and_tenant_to_none():
    uow = InMemoryUnitOfWork(agents=InMemoryAgentRepository())
    use_case = CreateAgentUseCase(uow=uow, password_hasher=FakePasswordHasher())
    command = CreateAgentCommand(name="Bob", email="bob@test.com", team="Sales", password="x")
    saved = use_case.execute(command)
    assert saved.role == AgentRole.AGENT
    assert saved.tenant_id is None
