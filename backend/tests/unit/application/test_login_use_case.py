import pytest

from application.ports.output.token_service_port import TokenClaims
from application.use_cases.auth_use_cases import LoginUseCase
from domain.entities.agent import Agent
from domain.exceptions import InvalidCredentialsException
from domain.value_objects.enums import AgentRole
from tests.unit.mocks.fake_password_hasher import FakePasswordHasher
from tests.unit.mocks.fake_token_service import FakeTokenService
from tests.unit.mocks.in_memory_agent_repo import InMemoryAgentRepository
from tests.unit.mocks.in_memory_lead_repo import InMemoryLeadRepository
from tests.unit.mocks.in_memory_rule_repo import InMemoryRuleRepository
from tests.unit.mocks.in_memory_uow import InMemoryUnitOfWork

_TENANT_ID = "b1a2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d"


def _build_use_case(email, password, role=AgentRole.MANAGER, is_active=True, tenant_id=_TENANT_ID):
    hasher = FakePasswordHasher()
    agent_repo = InMemoryAgentRepository()
    agent = Agent.create(
        "Test Agent",
        email,
        "Sales",
        role=role,
        hashed_password=hasher.hash(password),
        is_active=is_active,
        tenant_id=tenant_id,
    )
    agent_repo.save(agent)
    uow = InMemoryUnitOfWork(InMemoryLeadRepository(), InMemoryRuleRepository(), agent_repo)
    use_case = LoginUseCase(uow=uow, password_hasher=hasher, token_service=FakeTokenService())
    return use_case, agent


def test_login_succeeds_with_correct_credentials():
    use_case, _ = _build_use_case("manager@test.com", "correct-password")
    token = use_case.execute(email="manager@test.com", password="correct-password")
    assert isinstance(token, str) and token


def test_issued_token_carries_the_agent_identity_role_and_tenant():
    """The claims are the contract the API layer relies on to build the
    request context, so they are asserted explicitly."""
    use_case, agent = _build_use_case("manager@test.com", "correct-password")
    token = use_case.execute(email="manager@test.com", password="correct-password")
    claims = FakeTokenService().verify(token)
    assert claims == TokenClaims(
        agent_id=str(agent.id),
        role="MANAGER",
        tenant_id=_TENANT_ID,
    )


def test_platform_admin_gets_a_null_tenant_claim():
    use_case, _ = _build_use_case(
        "admin@test.com", "correct-password", role=AgentRole.ADMIN, tenant_id=None
    )
    token = use_case.execute(email="admin@test.com", password="correct-password")
    assert FakeTokenService().verify(token).tenant_id is None


def test_login_fails_with_wrong_password():
    use_case, _ = _build_use_case("manager@test.com", "correct-password")
    with pytest.raises(InvalidCredentialsException):
        use_case.execute(email="manager@test.com", password="wrong-password")


def test_login_fails_for_unknown_email():
    use_case, _ = _build_use_case("manager@test.com", "correct-password")
    with pytest.raises(InvalidCredentialsException):
        use_case.execute(email="nobody@test.com", password="correct-password")


def test_login_fails_for_inactive_agent():
    use_case, _ = _build_use_case("manager@test.com", "correct-password", is_active=False)
    with pytest.raises(InvalidCredentialsException):
        use_case.execute(email="manager@test.com", password="correct-password")


def test_unknown_email_and_wrong_password_are_indistinguishable():
    """Both paths must raise the same exception so the response does not leak
    whether an account exists."""
    use_case, _ = _build_use_case("manager@test.com", "correct-password")
    with pytest.raises(InvalidCredentialsException) as unknown:
        use_case.execute(email="nobody@test.com", password="correct-password")
    with pytest.raises(InvalidCredentialsException) as wrong:
        use_case.execute(email="manager@test.com", password="wrong-password")
    assert unknown.value.message == wrong.value.message
