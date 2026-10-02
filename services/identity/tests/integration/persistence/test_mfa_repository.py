import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import uuid4

import pytest

from application.use_cases.mfa.mfa_login import MfaLoginUseCase
from domain.agents.agent import Agent
from domain.exceptions import InvalidMfaFactorException
from domain.mfa.agent_mfa import AgentMfa
from domain.sessions.auth_challenge import AuthChallenge
from domain.sessions.auth_session import AuthSession
from infrastructure.adapters.output.persistence.unit_of_work import PostgresUnitOfWork


def _race(callable_, workers=2):
    barrier = threading.Barrier(workers)

    def run(_):
        barrier.wait(timeout=10)
        return callable_()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(run, range(workers)))


@pytest.fixture
def agent_id(uow_factory):
    with uow_factory() as uow:
        return uow.agents.save(Agent.create("MFA", f"mfa_{uuid4().hex[:8]}@test.com")).id.value


@pytest.fixture
def enrolled(uow_factory, agent_id):
    with uow_factory() as uow:
        uow.mfa.save_pending(AgentMfa(agent_id, "ciphertext"))
        assert uow.mfa.confirm(agent_id, 1, datetime.now(timezone.utc))
    return agent_id


def test_a_pending_enrollment_is_confirmed_once_and_a_new_setup_resets_it(uow_factory, agent_id):
    now = datetime.now(timezone.utc)
    with uow_factory() as uow:
        uow.mfa.save_pending(AgentMfa(agent_id, "first"))
        assert uow.mfa.get(agent_id) == AgentMfa(agent_id, "first")
        assert uow.mfa.confirm(agent_id, 7, now) is True
        assert uow.mfa.confirm(agent_id, 8, now) is False
        assert uow.mfa.get(agent_id) == AgentMfa(agent_id, "first", now, 7)

        uow.mfa.save_pending(AgentMfa(agent_id, "second"))
        assert uow.mfa.get(agent_id) == AgentMfa(agent_id, "second")


def test_a_totp_step_is_accepted_only_when_newer_than_the_last(uow_factory, enrolled):
    with uow_factory() as uow:
        assert uow.mfa.claim_totp_step(enrolled, 1) is False
        assert uow.mfa.claim_totp_step(enrolled, 3) is True
        assert uow.mfa.claim_totp_step(enrolled, 2) is False


def test_totp_step_and_recovery_code_are_claimed_once_under_race(uow_factory, enrolled):
    now = datetime.now(timezone.utc)
    with uow_factory() as uow:
        uow.mfa.replace_recovery_codes(enrolled, ["hash"], now)

    def claim_totp():
        with uow_factory() as uow:
            return uow.mfa.claim_totp_step(enrolled, 2)

    def consume_recovery():
        with uow_factory() as uow:
            return uow.mfa.consume_recovery_code(enrolled, "hash", now)

    assert sorted(_race(claim_totp)) == [False, True]
    assert sorted(_race(consume_recovery)) == [False, True]


def test_replacing_recovery_codes_retires_the_old_ones_and_delete_drops_them_all(uow_factory, enrolled):
    now = datetime.now(timezone.utc)
    with uow_factory() as uow:
        uow.mfa.replace_recovery_codes(enrolled, ["old"], now)
        uow.mfa.replace_recovery_codes(enrolled, ["new-1", "new-2"], now)
        assert uow.mfa.consume_recovery_code(enrolled, "old", now) is False
        assert uow.mfa.consume_recovery_code(enrolled, "new-1", now) is True

        uow.mfa.delete(enrolled)
        assert uow.mfa.get(enrolled) is None
        count = uow.connection.execute("SELECT COUNT(*) AS n FROM mfa_recovery_codes").fetchone()["n"]
    assert count == 0


def test_challenge_attempt_reservation_is_capped_and_purpose_scoped(uow_factory, agent_id):
    now = datetime.now(timezone.utc)
    with uow_factory() as uow:
        uow.challenges.save(AuthChallenge("challenge", agent_id, "MFA_LOGIN", 0, now + timedelta(minutes=5), None, now))
        uow.challenges.save(AuthChallenge("other", agent_id, "OTHER", 0, now + timedelta(minutes=5), None, now))

    def reserve():
        with uow_factory() as uow:
            return uow.challenges.reserve_attempt("challenge", "MFA_LOGIN", now, 5)

    assert _race(reserve, workers=6).count(True) == 5
    with uow_factory() as uow:
        assert uow.challenges.reserve_attempt("other", "MFA_LOGIN", now, 5) is False


def test_rotating_an_mfa_challenge_returns_its_attempts_and_expiry(uow_factory, agent_id):
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=5)
    with uow_factory() as uow:
        uow.challenges.save(AuthChallenge("challenge", agent_id, "MFA_LOGIN", 4, expires_at, None, now))
    with uow_factory() as uow:
        previous = uow.challenges.invalidate_active_for_agent(agent_id, "MFA_LOGIN", now)
        assert uow.challenges.invalidate_active_for_agent(agent_id, "MFA_LOGIN", now) is None

    assert (previous.attempts, previous.expires_at) == (4, expires_at)


def test_disable_can_preserve_an_exact_current_session(uow_factory, agent_id):
    now = datetime.now(timezone.utc)
    with uow_factory() as uow:
        uow.sessions.save(AuthSession("keep", agent_id, now, now + timedelta(hours=1)))
        uow.sessions.save(AuthSession("revoke", agent_id, now, now + timedelta(hours=1)))
        uow.sessions.revoke_for_agent_except(agent_id, "keep", now)
    with uow_factory() as uow:
        assert uow.sessions.get_active("keep", now) is not None
        assert uow.sessions.get_active("revoke", now) is None


def test_lost_challenge_consumption_rolls_back_the_factor_claim(test_db, enrolled, monkeypatch):
    now = datetime.now(timezone.utc)
    token = "challenge-token"
    challenge_hash = sha256(token.encode()).hexdigest()
    with PostgresUnitOfWork(test_db) as uow:
        uow.challenges.save(AuthChallenge(challenge_hash, enrolled, "MFA_LOGIN", 0, now + timedelta(minutes=5), None, now))

    original_enter = PostgresUnitOfWork.__enter__

    def enter_with_failed_consume(self):
        entered = original_enter(self)
        entered.challenges.consume = lambda *_: False
        return entered

    monkeypatch.setattr(PostgresUnitOfWork, "__enter__", enter_with_failed_consume)

    class Crypto:
        def decrypt(self, ciphertext):
            return ciphertext

        def matching_step(self, *_):
            return 2

    with pytest.raises(InvalidMfaFactorException):
        MfaLoginUseCase(PostgresUnitOfWork(test_db), Crypto()).verify_login(token, "123456")

    monkeypatch.undo()
    with PostgresUnitOfWork(test_db) as uow:
        assert uow.mfa.get(enrolled).last_used_step == 1
        assert uow.challenges.resolve_active(challenge_hash, now).attempts == 0
