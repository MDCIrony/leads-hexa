from datetime import datetime, timezone

import pytest

from application.use_cases.auth_use_cases import SocialLoginUseCase
from domain.entities.agent import Agent
from domain.entities.agent_mfa import AgentMfa
from domain.exceptions import InvalidCredentialsException
from domain.value_objects.enums import AgentRole
from tests.unit.mocks.in_memory_agent_repo import InMemoryAgentRepository
from tests.unit.mocks.in_memory_uow import InMemoryUnitOfWork


def _subject(role=AgentRole.AGENT, is_active=True):
    agents = InMemoryAgentRepository()
    agent = Agent.create(
        "OAuth", "OAuth@Example.Test", role=role, is_active=is_active,
        tenant_id="b1a2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
    )
    agents.save(agent)
    uow = InMemoryUnitOfWork(agents=agents)
    return agent, uow, SocialLoginUseCase(uow, session_hours=8)


def test_first_verified_login_links_normalized_email_then_reuses_subject():
    agent, uow, use_case = _subject()

    first = use_case.execute("GOOGLE", "subject", "  OAUTH@example.test ", True)
    second = use_case.execute("GOOGLE", "subject", None, False)

    assert first.status == second.status == "AUTHENTICATED"
    identity = uow.social_identities.get_by_provider_subject("GOOGLE", "subject")
    assert identity is not None and identity.agent_id == agent.id.value
    assert identity.email_at_link == "oauth@example.test"


@pytest.mark.parametrize("role,is_active", [(AgentRole.INTEGRATION, True), (AgentRole.AGENT, False)])
def test_social_login_rejects_non_human_or_inactive_agents(role, is_active):
    _, uow, use_case = _subject(role, is_active)

    with pytest.raises(InvalidCredentialsException):
        use_case.execute("GITHUB", "subject", "oauth@example.test", True)

    assert not uow.social_identities.items


def test_social_login_rejects_unverified_or_unknown_email():
    _, uow, use_case = _subject()

    with pytest.raises(InvalidCredentialsException):
        use_case.execute("GOOGLE", "subject", "oauth@example.test", False)
    with pytest.raises(InvalidCredentialsException):
        use_case.execute("GOOGLE", "different", "missing@example.test", True)

    assert not uow.social_identities.items


def test_social_login_returns_the_existing_mfa_challenge_instead_of_a_session():
    agent, uow, use_case = _subject()
    uow.mfa.items[agent.id.value] = AgentMfa(
        agent.id.value, "ciphertext", enabled_at=datetime.now(timezone.utc)
    )

    result = use_case.execute("GITHUB", "subject", agent.email, True)

    assert result.status == "MFA_REQUIRED"
    assert not uow.sessions.items


def test_subject_and_agent_provider_collisions_do_not_create_another_link():
    agent, uow, use_case = _subject()
    use_case.execute("GOOGLE", "first", agent.email, True)

    with pytest.raises(InvalidCredentialsException):
        use_case.execute("GOOGLE", "second", agent.email, True)

    assert len(uow.social_identities.items) == 1
