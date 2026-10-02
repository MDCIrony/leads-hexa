from datetime import datetime, timedelta, timezone
from hashlib import sha256

import pytest

from application.use_cases.auth.login import LoginUseCase
from application.use_cases.mfa.enrollment import MfaEnrollmentUseCase
from application.use_cases.mfa.mfa_login import MfaLoginUseCase
from domain.agents.agent import Agent
from domain.exceptions import InvalidCredentialsException, InvalidMfaFactorException
from domain.sessions.auth_challenge import AuthChallenge
from domain.sessions.auth_session import AuthSession
from domain.value_objects.agent_role import AgentRole
from tests.unit.application.doubles.services import VALID_TOTP, FakeMfaCrypto, FakePasswordHasher
from tests.unit.application.doubles.uow import InMemoryUnitOfWork


def _subject():
    hasher = FakePasswordHasher()
    uow = InMemoryUnitOfWork()
    agent = uow.agents.save(Agent.create(
        "MFA", "mfa@test.com", role=AgentRole.MANAGER,
        hashed_password=hasher.hash("correct-password"), tenant_id="b1a2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
    ))
    crypto = FakeMfaCrypto()
    return agent, uow, LoginUseCase(uow, hasher), MfaEnrollmentUseCase(uow, hasher, crypto), MfaLoginUseCase(uow, crypto)


def _other_session(uow, agent, token="other-session"):
    now = datetime.now(timezone.utc)
    uow.sessions.save(AuthSession(sha256(token.encode()).hexdigest(), agent.id.value, now, now + timedelta(hours=1)))
    return sha256(token.encode()).hexdigest()


def test_setup_confirm_and_mfa_login_create_no_password_only_session():
    agent, uow, login, enrollment, _ = _subject()

    setup = enrollment.setup(agent, "correct-password")
    recovery_codes = enrollment.confirm(agent, "current-session", VALID_TOTP)
    result = login.execute(agent.email, "correct-password")

    assert setup.secret == "pending-secret"
    assert len(recovery_codes) == 8
    assert all(len(code) == 32 for code in recovery_codes)
    assert result.status == "MFA_REQUIRED"
    assert sha256(result.token.encode()).hexdigest() not in uow.sessions.items


def test_setup_needs_the_password_and_cannot_overwrite_an_enabled_factor():
    agent, _, _, enrollment, _ = _subject()
    with pytest.raises(InvalidCredentialsException):
        enrollment.setup(agent, "wrong-password")
    enrollment.setup(agent, "correct-password")
    enrollment.confirm(agent, "current-session", VALID_TOTP)
    with pytest.raises(InvalidCredentialsException):
        enrollment.setup(agent, "correct-password")


def test_recovery_code_login_is_single_use():
    agent, _, login, enrollment, mfa_login = _subject()
    enrollment.setup(agent, "correct-password")
    recovery_codes = enrollment.confirm(agent, "current-session", VALID_TOTP)
    challenge = login.execute(agent.email, "correct-password")

    authenticated = mfa_login.verify_login(challenge.token, recovery_codes[0])

    assert authenticated.status == "AUTHENTICATED"
    with pytest.raises(InvalidMfaFactorException):
        mfa_login.verify_login(challenge.token, recovery_codes[0])


def test_a_totp_step_already_used_cannot_log_in_again():
    agent, _, login, enrollment, mfa_login = _subject()
    enrollment.setup(agent, "correct-password")
    enrollment.confirm(agent, "current-session", VALID_TOTP)  # confirms step 100
    challenge = login.execute(agent.email, "correct-password")

    with pytest.raises(InvalidMfaFactorException) as error:
        mfa_login.verify_login(challenge.token, VALID_TOTP)
    assert error.value.terminal is False


def test_confirming_mfa_preserves_current_session_and_revokes_others():
    agent, uow, login, enrollment, _ = _subject()
    current = login.execute(agent.email, "correct-password")
    other = _other_session(uow, agent)

    enrollment.setup(agent, "correct-password")
    enrollment.confirm(agent, current.token, VALID_TOTP)

    assert uow.sessions.items[sha256(current.token.encode()).hexdigest()].revoked_at is None
    assert uow.sessions.items[other].revoked_at is not None


def test_regenerating_recovery_codes_retires_the_previous_ones():
    agent, _, login, enrollment, mfa_login = _subject()
    enrollment.setup(agent, "correct-password")
    old_codes = enrollment.confirm(agent, "current-session", VALID_TOTP)

    new_codes = enrollment.regenerate_recovery_codes(agent, "correct-password", old_codes[0])

    challenge = login.execute(agent.email, "correct-password")
    with pytest.raises(InvalidMfaFactorException):
        mfa_login.verify_login(challenge.token, old_codes[1])
    assert mfa_login.verify_login(challenge.token, new_codes[0]).status == "AUTHENTICATED"


def test_disable_preserves_the_current_session_and_revokes_the_others():
    agent, uow, login, enrollment, mfa_login = _subject()
    enrollment.setup(agent, "correct-password")
    recovery_codes = enrollment.confirm(agent, "current-session", VALID_TOTP)
    first = login.execute(agent.email, "correct-password")
    session = mfa_login.verify_login(first.token, recovery_codes[0])
    other = _other_session(uow, agent)

    enrollment.disable(agent, session.token, "correct-password", recovery_codes[1])

    assert uow.mfa.get(agent.id.value) is None
    assert uow.sessions.items[sha256(session.token.encode()).hexdigest()].revoked_at is None
    assert uow.sessions.items[other].revoked_at is not None


def test_successful_password_login_invalidates_stale_mfa_challenges():
    agent, uow, login, _, _ = _subject()
    now = datetime.now(timezone.utc)
    uow.challenges.save(AuthChallenge("stale", agent.id.value, "MFA_LOGIN", 0, now + timedelta(minutes=5), None, now))

    login.execute(agent.email, "correct-password")

    assert uow.challenges.resolve_active("stale", now) is None


def test_relogin_preserves_mfa_attempt_limit_and_window():
    agent, uow, login, enrollment, mfa_login = _subject()
    enrollment.setup(agent, "correct-password")
    enrollment.confirm(agent, "current-session", VALID_TOTP)
    challenge = login.execute(agent.email, "correct-password")

    for _ in range(5):
        with pytest.raises(InvalidMfaFactorException):
            mfa_login.verify_login(challenge.token, "wrong")
    now = datetime.now(timezone.utc)
    exhausted = uow.challenges.resolve_active(sha256(challenge.token.encode()).hexdigest(), now)
    replacement = login.execute(agent.email, "correct-password")
    active = uow.challenges.resolve_active(sha256(replacement.token.encode()).hexdigest(), now)

    assert exhausted is not None and active is not None
    assert active.attempts == 5
    assert active.expires_at == exhausted.expires_at
    with pytest.raises(InvalidMfaFactorException) as error:
        mfa_login.verify_login(replacement.token, "wrong")
    assert error.value.terminal is True


def test_verify_without_a_challenge_is_terminal():
    *_, mfa_login = _subject()
    with pytest.raises(InvalidMfaFactorException) as error:
        mfa_login.verify_login(None, VALID_TOTP)
    assert error.value.terminal is True
