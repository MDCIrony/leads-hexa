from datetime import datetime, timezone

import pytest

from application.use_cases.oauth.social_login import SocialLoginUseCase
from domain.agents.agent import Agent
from domain.exceptions import InvalidCredentialsException
from domain.mfa.agent_mfa import AgentMfa
from domain.value_objects.agent_role import AgentRole
from tests.unit.application.doubles.uow import InMemoryUnitOfWork


def _subject(role=AgentRole.AGENT, is_active=True):
    uow = InMemoryUnitOfWork()
    agent = uow.agents.save(Agent.create(
        "OAuth", "OAuth@Example.Test", role=role, is_active=is_active,
        tenant_id="b1a2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
    ))
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
    uow.mfa.items[agent.id.value] = AgentMfa(agent.id.value, "ciphertext", enabled_at=datetime.now(timezone.utc))

    result = use_case.execute("GITHUB", "subject", agent.email, True)

    assert result.status == "MFA_REQUIRED"
    assert not uow.sessions.items


def test_subject_and_agent_provider_collisions_do_not_create_another_link():
    agent, uow, use_case = _subject()
    use_case.execute("GOOGLE", "first", agent.email, True)

    with pytest.raises(InvalidCredentialsException):
        use_case.execute("GOOGLE", "second", agent.email, True)

    assert len(uow.social_identities.items) == 1


def test_a_linked_subject_of_a_since_deactivated_agent_is_rejected():
    agent, _, use_case = _subject()
    use_case.execute("GOOGLE", "subject", agent.email, True)
    agent.is_active = False

    with pytest.raises(InvalidCredentialsException):
        use_case.execute("GOOGLE", "subject", None, False)
