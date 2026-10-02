from hashlib import sha256

import pytest

from application.use_cases.auth.login import LoginUseCase
from domain.agents.agent import Agent
from domain.exceptions import InvalidCredentialsException
from domain.value_objects.agent_role import AgentRole
from tests.unit.application.doubles.services import FakePasswordHasher
from tests.unit.application.doubles.uow import InMemoryUnitOfWork

_TENANT_ID = "b1a2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d"


def _build_use_case(email, password, role=AgentRole.MANAGER, is_active=True):
    hasher = FakePasswordHasher()
    uow = InMemoryUnitOfWork()
    uow.agents.save(Agent.create(
        "Test Agent", email, role=role, hashed_password=hasher.hash(password),
        is_active=is_active, tenant_id=_TENANT_ID,
    ))
    return LoginUseCase(uow=uow, password_hasher=hasher), uow


def test_login_succeeds_with_correct_credentials():
    use_case, _ = _build_use_case("manager@test.com", "correct-password")
    result = use_case.execute(email="manager@test.com", password="correct-password")
    assert result.status == "AUTHENTICATED" and result.token


def test_login_normalizes_email_before_lookup():
    use_case, _ = _build_use_case("manager@test.com", "correct-password")
    result = use_case.execute(email="  MANAGER@Test.Com ", password="correct-password")
    assert result.status == "AUTHENTICATED" and result.token


def test_issued_session_is_stored_only_as_a_hash():
    use_case, uow = _build_use_case("manager@test.com", "correct-password")
    result = use_case.execute(email="manager@test.com", password="correct-password")
    assert result.token not in uow.sessions.items
    assert sha256(result.token.encode()).hexdigest() in uow.sessions.items


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


def test_login_fails_for_an_integration_credential_even_with_the_right_secret():
    """A machine principal's only door in is its integration credential."""
    use_case, _ = _build_use_case("integration@acme.invalid", "correct-password", role=AgentRole.INTEGRATION)
    with pytest.raises(InvalidCredentialsException):
        use_case.execute(email="integration@acme.invalid", password="correct-password")


def test_unknown_email_and_wrong_password_are_indistinguishable():
    """Both paths raise the same exception so the response does not leak whether an account exists."""
    use_case, _ = _build_use_case("manager@test.com", "correct-password")
    with pytest.raises(InvalidCredentialsException) as unknown:
        use_case.execute(email="nobody@test.com", password="correct-password")
    with pytest.raises(InvalidCredentialsException) as wrong:
        use_case.execute(email="manager@test.com", password="wrong-password")
    assert unknown.value.message == wrong.value.message
