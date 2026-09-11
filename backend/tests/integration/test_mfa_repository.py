import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from application.use_cases.auth_use_cases import MfaUseCase
from domain.entities.agent_mfa import AgentMfa
from domain.entities.auth_challenge import AuthChallenge
from domain.entities.auth_session import AuthSession
from domain.exceptions import InvalidMfaFactorException
from infrastructure.adapters.output.persistence.connection import RawSqlDatabase
from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
from tests.unit.mocks.fake_password_hasher import FakePasswordHasher


@pytest.fixture
def mfa_db(dsn_of_test_db):
    database = RawSqlDatabase(dsn=dsn_of_test_db)
    yield database
    database.close()


def _agent(database):
    agent_id = uuid4()
    with database.get_connection(autocommit=True) as conn:
        conn.execute(
            "INSERT INTO agents (id, name, email) VALUES (%s, %s, %s)",
            (agent_id, "MFA", f"mfa_{agent_id.hex[:8]}@test.com"),
        )
    return agent_id


def _mfa(database, agent_id):
    now = datetime.now(timezone.utc)
    with PostgresUnitOfWork(database) as uow:
        uow.mfa.save_pending(AgentMfa(agent_id, "ciphertext"))
        assert uow.mfa.confirm(agent_id, 1, now)


def test_totp_step_and_recovery_code_are_claimed_once_under_race(mfa_db):
    agent_id = _agent(mfa_db)
    _mfa(mfa_db, agent_id)
    now = datetime.now(timezone.utc)
    with PostgresUnitOfWork(mfa_db) as uow:
        uow.mfa.replace_recovery_codes(agent_id, ["hash"], now)
    barrier = threading.Barrier(2)

    def claim_totp():
        barrier.wait(timeout=10)
        with PostgresUnitOfWork(mfa_db) as uow:
            return uow.mfa.claim_totp_step(agent_id, 2)

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: claim_totp(), range(2))) == [False, True]

    barrier = threading.Barrier(2)

    def consume_recovery():
        barrier.wait(timeout=10)
        with PostgresUnitOfWork(mfa_db) as uow:
            return uow.mfa.consume_recovery_code(agent_id, "hash", now)

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: consume_recovery(), range(2))) == [False, True]


def test_challenge_attempt_reservation_is_capped_and_purpose_scoped(mfa_db):
    agent_id = _agent(mfa_db)
    now = datetime.now(timezone.utc)
    with PostgresUnitOfWork(mfa_db) as uow:
        uow.challenges.save(AuthChallenge(
            "challenge", agent_id, "MFA_LOGIN", 0, now + timedelta(minutes=5), None, now,
        ))
        uow.challenges.save(AuthChallenge(
            "other", agent_id, "OTHER", 0, now + timedelta(minutes=5), None, now,
        ))
    barrier = threading.Barrier(6)

    def reserve():
        barrier.wait(timeout=10)
        with PostgresUnitOfWork(mfa_db) as uow:
            return uow.challenges.reserve_attempt("challenge", "MFA_LOGIN", now, 5)

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: reserve(), range(6)))
    assert results.count(True) == 5
    with PostgresUnitOfWork(mfa_db) as uow:
        assert uow.challenges.reserve_attempt("other", "MFA_LOGIN", now, 5) is False


def test_rotating_mfa_challenge_returns_its_attempts_and_expiry(mfa_db):
    agent_id = _agent(mfa_db)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=5)
    with PostgresUnitOfWork(mfa_db) as uow:
        uow.challenges.save(AuthChallenge(
            "challenge", agent_id, "MFA_LOGIN", 4, expires_at, None, now,
        ))
    with PostgresUnitOfWork(mfa_db) as uow:
        previous = uow.challenges.invalidate_active_for_agent(agent_id, "MFA_LOGIN", now)

    assert previous is not None
    assert previous.attempts == 4
    assert previous.expires_at == expires_at


def test_disable_can_preserve_an_exact_current_session(mfa_db):
    agent_id = _agent(mfa_db)
    now = datetime.now(timezone.utc)
    with PostgresUnitOfWork(mfa_db) as uow:
        uow.sessions.save(AuthSession("keep", agent_id, now, now + timedelta(hours=1)))
        uow.sessions.save(AuthSession("revoke", agent_id, now, now + timedelta(hours=1)))
        uow.sessions.revoke_for_agent_except(agent_id, "keep", now)
    with PostgresUnitOfWork(mfa_db) as uow:
        assert uow.sessions.get_active("keep", now) is not None
        assert uow.sessions.get_active("revoke", now) is None


def test_lost_challenge_consumption_rolls_back_factor_claim(mfa_db, monkeypatch):
    agent_id = _agent(mfa_db)
    now = datetime.now(timezone.utc)
    token = "challenge-token"
    from hashlib import sha256
    with PostgresUnitOfWork(mfa_db) as uow:
        uow.mfa.save_pending(AgentMfa(agent_id, "ciphertext"))
        assert uow.mfa.confirm(agent_id, 1, now)
        uow.challenges.save(AuthChallenge(
            sha256(token.encode()).hexdigest(), agent_id, "MFA_LOGIN", 0,
            now + timedelta(minutes=5), None, now,
        ))

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
        MfaUseCase(PostgresUnitOfWork(mfa_db), FakePasswordHasher(), Crypto()).verify_login(token, "123456")

    with PostgresUnitOfWork(mfa_db) as uow:
        enrollment = uow.mfa.get(agent_id)
        challenge = uow.challenges.resolve_active(sha256(token.encode()).hexdigest(), now)
    assert enrollment.last_used_step == 1
    assert challenge.attempts == 0
