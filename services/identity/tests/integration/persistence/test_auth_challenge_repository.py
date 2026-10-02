"""Runs against real PostgreSQL: constraints, expiry comparisons and the single-use
races are invisible to the in-memory double."""
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg
import pytest

from domain.sessions.auth_challenge import AuthChallenge
from infrastructure.adapters.output.persistence.challenge_repository import PostgresAuthChallengeRepository


@pytest.fixture
def repo(test_db):
    with test_db.get_connection(autocommit=True) as conn:
        yield PostgresAuthChallengeRepository(conn)


def _challenge(token_hash="hash", purpose="LOGIN", minutes=5, agent_id=None, now=None, attempts=0):
    now = now or datetime.now(timezone.utc)
    return AuthChallenge(token_hash, agent_id, purpose, attempts, now + timedelta(minutes=minutes), None, now)


def _race(callable_, workers=2):
    barrier = threading.Barrier(workers)

    def run(_):
        barrier.wait(timeout=10)
        return callable_()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(run, range(workers)))


def test_create_and_resolve_round_trips_every_field(repo, test_db):
    now = datetime.now(timezone.utc)
    agent_id = uuid4()
    with test_db.get_connection(autocommit=True) as conn:
        conn.execute("INSERT INTO agents (id, name, email) VALUES (%s, 'Agent', %s)", (agent_id, f"{agent_id}@t.test"))
    saved = _challenge(agent_id=agent_id, now=now)
    repo.save(saved)

    assert repo.resolve_active("hash", now) == saved


def test_agent_stays_nullable_until_the_external_identity_resolves(repo):
    now = datetime.now(timezone.utc)
    repo.save(_challenge(now=now))

    assert repo.resolve_active("hash", now).agent_id is None


def test_resolve_rejects_altered_expired_and_consumed(repo):
    now = datetime.now(timezone.utc)
    repo.save(_challenge("live", now=now))
    repo.save(_challenge("old", minutes=-5, now=now))
    repo.save(_challenge("used", now=now))
    assert repo.consume("used", now) is True

    assert repo.resolve_active("live-tampered", now) is None
    assert repo.resolve_active("old", now) is None
    assert repo.resolve_active("used", now) is None


def test_increment_moves_attempts_by_exactly_one_and_only_on_a_live_challenge(repo):
    now = datetime.now(timezone.utc)
    repo.save(_challenge("live", now=now, attempts=2))
    repo.save(_challenge("old", minutes=-5, now=now))

    assert repo.increment_attempts("live", now) is True
    assert repo.resolve_active("live", now).attempts == 3
    assert repo.increment_attempts("old", now) is False
    assert repo.increment_attempts("missing", now) is False


def test_consume_fixes_consumed_at_exactly_once(repo):
    first = datetime.now(timezone.utc)
    repo.save(_challenge(now=first))

    assert repo.consume("hash", first) is True
    assert repo.consume("hash", first + timedelta(seconds=30)) is False
    row = repo.connection.execute("SELECT consumed_at FROM auth_challenges WHERE token_hash = 'hash'").fetchone()
    assert row["consumed_at"] == first


def test_consume_of_an_expired_challenge_fails(repo):
    now = datetime.now(timezone.utc)
    repo.save(_challenge(minutes=-5, now=now))

    assert repo.consume("hash", now) is False


def test_two_transactions_consume_the_same_challenge_only_once(repo, uow_factory):
    """The single UPDATE ... WHERE consumed_at IS NULL is the whole of the atomicity."""
    now = datetime.now(timezone.utc)
    repo.save(_challenge(now=now))

    def consume():
        with uow_factory() as uow:
            return uow.challenges.consume("hash", now)

    assert sorted(_race(consume)) == [False, True]


def test_an_oauth_challenge_is_consumed_once_and_only_with_its_state(repo, uow_factory):
    now = datetime.now(timezone.utc)
    repo.save(AuthChallenge(
        "oauth", None, "OAUTH_LOGIN", 0, now + timedelta(minutes=5), None, now,
        provider="GOOGLE", state_hash="state", pkce_verifier="verifier", return_path="/home",
    ))
    assert repo.consume_oauth("oauth", "GOOGLE", "other-state", now) is None
    assert repo.consume_oauth("oauth", "GITHUB", "state", now) is None

    def consume():
        with uow_factory() as uow:
            return uow.challenges.consume_oauth("oauth", "GOOGLE", "state", now)

    results = _race(consume)
    assert sum(result is not None for result in results) == 1
    assert next(r for r in results if r).pkce_verifier == "verifier"


def test_blank_purpose_and_negative_attempts_hit_the_constraints(repo):
    """The entity refuses these first; the CHECKs stop any writer that bypasses it."""
    now = datetime.now(timezone.utc)
    insert = (
        "INSERT INTO auth_challenges (token_hash, purpose, attempts, expires_at, created_at)"
        " VALUES (%s, %s, %s, %s, %s)"
    )
    with pytest.raises(psycopg.IntegrityError):
        repo.connection.execute(insert, ("blank", "  ", 0, now + timedelta(minutes=5), now))
    with pytest.raises(psycopg.IntegrityError):
        repo.connection.execute(insert, ("negative", "LOGIN", -1, now + timedelta(minutes=5), now))


def test_misses_return_false_or_none_without_raising_or_logging(caplog, repo):
    """Nothing raised and nothing logged on a miss: no line for a token hash to leak into."""
    now = datetime.now(timezone.utc)
    secret = "s3cr3t-bearing-hash"

    assert repo.resolve_active(secret, now) is None
    assert repo.increment_attempts(secret, now) is False
    assert repo.consume(secret, now) is False
    assert "s3cr3t" not in caplog.text
