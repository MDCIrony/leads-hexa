"""Persistence contract of the minimal auth-challenge store (plan 02).

Runs against real PostgreSQL: constraints, expiry comparisons and the
single-use consume race are invisible to the in-memory double. Behaviour only:
rows in, rows out, rowcounts — never the raw token outside the operation.
"""
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import psycopg
import pytest

from domain.entities.auth_challenge import AuthChallenge
from infrastructure.adapters.output.persistence.connection import RawSqlDatabase
from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
from infrastructure.adapters.output.persistence.raw_sql_auth_challenge_repository import (
    RawSqlAuthChallengeRepository,
)


@pytest.fixture
def challenge_db(dsn_of_test_db):
    """This module's own pool, same reason as concurrent_db in
    test_concurrent_intake: borrowing extra connections out of the
    suite-wide pool would disturb the tests that assert on its size."""
    database = RawSqlDatabase(dsn=dsn_of_test_db)
    yield database
    database.close()


def _challenge(token_hash="hash", purpose="LOGIN", minutes=5, agent_id=None, now=None):
    now = now or datetime.now(timezone.utc)
    return AuthChallenge(
        token_hash, agent_id, purpose, 0,
        now + timedelta(minutes=minutes), None, now,
    )


def _save(database, challenge):
    with database.get_connection(autocommit=True) as conn:
        RawSqlAuthChallengeRepository(conn).save(challenge)


def test_create_and_resolve_round_trips_every_field(challenge_db):
    now = datetime.now(timezone.utc)
    agent_id = uuid.uuid4()
    with challenge_db.get_connection(autocommit=True) as conn:
        conn.execute(
            "INSERT INTO agents (id, name, email) VALUES (%s, %s, %s)",
            (agent_id, "Agent", f"chall_{uuid.uuid4().hex[:8]}@test.com"),
        )
    _save(challenge_db, AuthChallenge(
        "hash", agent_id, "LOGIN", 0,
        now + timedelta(minutes=5), None, now,
    ))

    with challenge_db.get_connection(autocommit=True) as conn:
        resolved = RawSqlAuthChallengeRepository(conn).resolve_active("hash", now)

    assert resolved is not None
    assert resolved.token_hash == "hash"
    assert resolved.agent_id == agent_id
    assert resolved.purpose == "LOGIN"
    assert resolved.attempts == 0
    assert resolved.consumed_at is None


def test_agent_stays_nullable_until_the_external_identity_resolves(challenge_db):
    now = datetime.now(timezone.utc)
    _save(challenge_db, _challenge("hash", now=now))

    with challenge_db.get_connection(autocommit=True) as conn:
        resolved = RawSqlAuthChallengeRepository(conn).resolve_active("hash", now)

    assert resolved is not None
    assert resolved.agent_id is None


def test_resolve_rejects_altered_expired_and_consumed(challenge_db):
    now = datetime.now(timezone.utc)
    _save(challenge_db, _challenge("live", now=now))
    _save(challenge_db, _challenge("old", minutes=-5, now=now))
    consumed = _challenge("used", now=now)
    _save(challenge_db, consumed)
    with challenge_db.get_connection(autocommit=True) as conn:
        repo = RawSqlAuthChallengeRepository(conn)
        assert repo.consume("used", now) is True

    with challenge_db.get_connection(autocommit=True) as conn:
        repo = RawSqlAuthChallengeRepository(conn)
        assert repo.resolve_active("live-tampered", now) is None
        assert repo.resolve_active("old", now) is None
        assert repo.resolve_active("used", now) is None


def test_increment_moves_attempts_by_exactly_one(challenge_db):
    now = datetime.now(timezone.utc)
    challenge = _challenge("hash", now=now)
    _save(challenge_db, AuthChallenge(**{**challenge.__dict__, "attempts": 2}))

    with challenge_db.get_connection(autocommit=True) as conn:
        assert RawSqlAuthChallengeRepository(conn).increment_attempts("hash", now) is True

    with challenge_db.get_connection(autocommit=True) as conn:
        resolved = RawSqlAuthChallengeRepository(conn).resolve_active("hash", now)
    assert resolved.attempts == 3


def test_increment_only_touches_a_live_challenge(challenge_db):
    now = datetime.now(timezone.utc)
    _save(challenge_db, _challenge("live", now=now))
    _save(challenge_db, _challenge("old", minutes=-5, now=now))
    _save(challenge_db, _challenge("used", now=now))
    with challenge_db.get_connection(autocommit=True) as conn:
        assert RawSqlAuthChallengeRepository(conn).consume("used", now) is True

    with challenge_db.get_connection(autocommit=True) as conn:
        repo = RawSqlAuthChallengeRepository(conn)
        assert repo.increment_attempts("old", now) is False
        assert repo.increment_attempts("used", now) is False
        assert repo.increment_attempts("missing", now) is False

    with challenge_db.get_connection(autocommit=True) as conn:
        row = conn.execute(
            "SELECT attempts FROM auth_challenges WHERE token_hash = %s", ("old",)
        ).fetchone()
    assert row["attempts"] == 0


def test_consume_fixes_consumed_at_exactly_once(challenge_db):
    first = datetime.now(timezone.utc)
    _save(challenge_db, _challenge("hash", now=first))

    with challenge_db.get_connection(autocommit=True) as conn:
        repo = RawSqlAuthChallengeRepository(conn)
        assert repo.consume("hash", first) is True
        assert repo.consume("hash", first + timedelta(seconds=30)) is False
        stored = conn.execute(
            "SELECT consumed_at FROM auth_challenges WHERE token_hash = %s", ("hash",)
        ).fetchone()
    assert stored["consumed_at"] == first


def test_consume_of_an_expired_challenge_fails(challenge_db):
    now = datetime.now(timezone.utc)
    _save(challenge_db, _challenge("hash", minutes=-5, now=now))

    with challenge_db.get_connection(autocommit=True) as conn:
        assert RawSqlAuthChallengeRepository(conn).consume("hash", now) is False


def test_two_transactions_consume_the_same_challenge_only_once(challenge_db):
    """The single UPDATE ... WHERE consumed_at IS NULL is the whole of the
    atomicity: two backends racing on the same row must split True/False."""
    now = datetime.now(timezone.utc)
    _save(challenge_db, _challenge("hash", now=now))
    barrier = threading.Barrier(2)

    def consume():
        barrier.wait(timeout=10)
        uow = PostgresUnitOfWork(challenge_db)
        with uow:
            return uow.challenges.consume("hash", now)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: consume(), range(2)))

    assert sorted(results) == [False, True]


def test_blank_purpose_and_negative_attempts_hit_the_constraints(challenge_db):
    """The entity rejects these first (unit-tested); the CHECKs are the second
    lock for any writer that bypasses it, so they are asserted here with raw
    SQL rather than through the validating entity."""
    now = datetime.now(timezone.utc)
    with challenge_db.get_connection(autocommit=True) as conn:
        with pytest.raises(psycopg.IntegrityError):
            conn.execute(
                "INSERT INTO auth_challenges (token_hash, agent_id, purpose, attempts, expires_at, consumed_at, created_at)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s)",
                ("blank", None, "  ", 0, now + timedelta(minutes=5), None, now),
            )
        with pytest.raises(psycopg.IntegrityError):
            conn.execute(
                "INSERT INTO auth_challenges (token_hash, agent_id, purpose, attempts, expires_at, consumed_at, created_at)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s)",
                ("negative", None, "LOGIN", -1, now + timedelta(minutes=5), None, now),
            )


def test_failures_return_false_or_none_without_raising(caplog, challenge_db):
    """Nothing is raised and nothing is logged on a miss, so there is no
    exception or log line left for a token, hash or secret to leak into."""
    now = datetime.now(timezone.utc)
    secret = "s3cr3t-bearing-hash"
    with challenge_db.get_connection(autocommit=True) as conn:
        repo = RawSqlAuthChallengeRepository(conn)
        assert repo.resolve_active(secret, now) is None
        assert repo.increment_attempts(secret, now) is False
        assert repo.consume(secret, now) is False
    assert "s3cr3t" not in caplog.text
