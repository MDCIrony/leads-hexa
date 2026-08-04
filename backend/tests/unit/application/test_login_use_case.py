import pytest
from application.use_cases.auth_use_cases import LoginUseCase
from domain.entities.agent import Agent
from domain.exceptions import InvalidCredentialsException
from domain.value_objects.enums import AgentRole
from infrastructure.security.password_hasher import hash_password
from tests.unit.mocks.in_memory_agent_repo import InMemoryAgentRepository
from tests.unit.mocks.in_memory_lead_repo import InMemoryLeadRepository
from tests.unit.mocks.in_memory_rule_repo import InMemoryRuleRepository
from tests.unit.mocks.in_memory_uow import InMemoryUnitOfWork


def _build_uow_with_agent(email: str, password: str, role: AgentRole, is_active: bool = True):
    agent_repo = InMemoryAgentRepository()
    lead_repo = InMemoryLeadRepository()
    rule_repo = InMemoryRuleRepository()
    agent = Agent.create("Test Agent", email, "Sales", role=role, hashed_password=hash_password(password), is_active=is_active)
    agent_repo.save(agent)
    uow = InMemoryUnitOfWork(lead_repo, rule_repo, agent_repo)
    return uow, agent


def test_login_succeeds_with_correct_credentials():
    uow, agent = _build_uow_with_agent("admin@test.com", "correct-password", AgentRole.ADMIN)
    use_case = LoginUseCase(uow=uow)
    token = use_case.execute(email="admin@test.com", password="correct-password")
    assert isinstance(token, str) and len(token) > 0


def test_login_fails_with_wrong_password():
    uow, _ = _build_uow_with_agent("admin@test.com", "correct-password", AgentRole.ADMIN)
    use_case = LoginUseCase(uow=uow)
    with pytest.raises(InvalidCredentialsException):
        use_case.execute(email="admin@test.com", password="wrong-password")


def test_login_fails_for_unknown_email():
    uow, _ = _build_uow_with_agent("admin@test.com", "correct-password", AgentRole.ADMIN)
    use_case = LoginUseCase(uow=uow)
    with pytest.raises(InvalidCredentialsException):
        use_case.execute(email="nobody@test.com", password="correct-password")


def test_login_fails_for_inactive_agent():
    uow, _ = _build_uow_with_agent("admin@test.com", "correct-password", AgentRole.ADMIN, is_active=False)
    use_case = LoginUseCase(uow=uow)
    with pytest.raises(InvalidCredentialsException):
        use_case.execute(email="admin@test.com", password="correct-password")
