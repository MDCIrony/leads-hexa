import uuid
import pytest
from application.dtos.queries import GetAgentQuery
from application.use_cases.agent_use_cases import GetAgentUseCase
from domain.exceptions import AgentNotFoundException
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
        use_case.execute(GetAgentQuery(agent_id=uuid.uuid4()))

    assert exc_info.value.error_code == "AGENT_NOT_FOUND"
    assert exc_info.value.status_code == 404
