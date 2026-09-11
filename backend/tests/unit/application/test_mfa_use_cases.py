from datetime import datetime, timedelta, timezone
from hashlib import sha256

import pytest

from application.use_cases.auth_use_cases import LoginUseCase, MfaUseCase
from domain.entities.agent import Agent
from domain.entities.auth_challenge import AuthChallenge
from domain.exceptions import InvalidMfaFactorException
from domain.value_objects.enums import AgentRole
from tests.unit.mocks.fake_password_hasher import FakePasswordHasher
from tests.unit.mocks.in_memory_agent_repo import InMemoryAgentRepository
from tests.unit.mocks.in_memory_uow import InMemoryUnitOfWork


class FakeMfaCrypto:
    def generate_secret(self):
        return "pending-secret"

    def encrypt(self, secret):
        return f"encrypted:{secret}"

    def decrypt(self, ciphertext):
        return ciphertext.removeprefix("encrypted:")

    def matching_step(self, secret, code, now):
        return 100 if secret == "pending-secret" and code == "123456" else None

    def provisioning_uri(self, secret, email):
        return f"otpauth://totp/Lead%20Router:{email}?secret={secret}"


def _subject():
    hasher = FakePasswordHasher()
    agents = InMemoryAgentRepository()
    agent = Agent.create(
        "MFA", "mfa@test.com", role=AgentRole.MANAGER,
        hashed_password=hasher.hash("correct-password"), tenant_id="b1a2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
    )
    agents.save(agent)
    uow = InMemoryUnitOfWork(agents=agents)
    return agent, uow, LoginUseCase(uow, hasher), MfaUseCase(uow, hasher, FakeMfaCrypto())


def test_setup_confirm_and_mfa_login_create_no_password_only_session():
    agent, uow, login, mfa = _subject()

    setup = mfa.setup(agent, "correct-password")
    recovery_codes = mfa.confirm(agent, "current-session", "123456")
    result = login.execute(agent.email, "correct-password")

    assert setup.secret == "pending-secret"
    assert len(recovery_codes) == 8
    assert all(len(code) == 32 for code in recovery_codes)
    assert result.status == "MFA_REQUIRED"
    assert sha256(result.token.encode()).hexdigest() not in uow.sessions.items


def test_totp_login_is_single_use_and_recovery_code_is_consumed_once():
    agent, _, login, mfa = _subject()
    mfa.setup(agent, "correct-password")
    recovery_codes = mfa.confirm(agent, "current-session", "123456")
    challenge = login.execute(agent.email, "correct-password")

    authenticated = mfa.verify_login(challenge.token, recovery_codes[0])

    assert authenticated.status == "AUTHENTICATED"
    with pytest.raises(Exception):
        mfa.verify_login(challenge.token, recovery_codes[0])


def test_confirming_mfa_preserves_current_session_and_revokes_others():
    agent, uow, login, mfa = _subject()
    current = login.execute(agent.email, "correct-password")
    other_token = "other-session"
    from domain.entities.auth_session import AuthSession
    now = datetime.now(timezone.utc)
    uow.sessions.save(AuthSession(
        sha256(other_token.encode()).hexdigest(), agent.id.value, now, now + timedelta(hours=1),
    ))

    mfa.setup(agent, "correct-password")
    mfa.confirm(agent, current.token, "123456")

    assert uow.sessions.items[sha256(current.token.encode()).hexdigest()].revoked_at is None
    assert uow.sessions.items[sha256(other_token.encode()).hexdigest()].revoked_at is not None


def test_disable_preserves_the_current_session_and_revokes_the_others():
    agent, uow, login, mfa = _subject()
    mfa.setup(agent, "correct-password")
    recovery_codes = mfa.confirm(agent, "current-session", "123456")
    first = login.execute(agent.email, "correct-password")
    session = mfa.verify_login(first.token, recovery_codes[0])
    other_token = "other-session"
    from domain.entities.auth_session import AuthSession
    from datetime import timedelta
    uow.sessions.save(AuthSession(
        sha256(other_token.encode()).hexdigest(), agent.id.value,
        datetime.now(timezone.utc), datetime.now(timezone.utc) + timedelta(hours=1),
    ))

    mfa.disable(agent, session.token, "correct-password", recovery_codes[1])

    assert uow.mfa.get(agent.id.value) is None
    assert uow.sessions.items[sha256(session.token.encode()).hexdigest()].revoked_at is None
    assert uow.sessions.items[sha256(other_token.encode()).hexdigest()].revoked_at is not None


def test_successful_password_login_invalidates_stale_mfa_challenges():
    agent, uow, login, _ = _subject()
    now = datetime.now(timezone.utc)
    uow.challenges.save(AuthChallenge(
        "stale", agent.id.value, "MFA_LOGIN", 0, now + timedelta(minutes=5), None, now,
    ))

    login.execute(agent.email, "correct-password")

    assert uow.challenges.resolve_active("stale", now) is None


def test_relogin_preserves_mfa_attempt_limit_and_window():
    agent, uow, login, mfa = _subject()
    mfa.setup(agent, "correct-password")
    mfa.confirm(agent, "current-session", "123456")
    challenge = login.execute(agent.email, "correct-password")

    for _ in range(5):
        with pytest.raises(InvalidMfaFactorException):
            mfa.verify_login(challenge.token, "wrong")
    exhausted = uow.challenges.resolve_active(sha256(challenge.token.encode()).hexdigest(), datetime.now(timezone.utc))
    replacement = login.execute(agent.email, "correct-password")
    active = uow.challenges.resolve_active(sha256(replacement.token.encode()).hexdigest(), datetime.now(timezone.utc))

    assert exhausted is not None
    assert active is not None
    assert active.attempts == 5
    assert active.expires_at == exhausted.expires_at
    with pytest.raises(InvalidMfaFactorException):
        mfa.verify_login(replacement.token, "wrong")
