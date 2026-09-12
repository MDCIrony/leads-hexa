import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg
import pytest

from domain.entities.auth_challenge import AuthChallenge
from domain.entities.social_identity import SocialIdentity
from infrastructure.adapters.output.persistence.connection import RawSqlDatabase
from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork


@pytest.fixture
def social_db(dsn_of_test_db):
    database = RawSqlDatabase(dsn=dsn_of_test_db)
    yield database
    database.close()


def _agent(database):
    agent_id = uuid4()
    with database.get_connection(autocommit=True) as conn:
        conn.execute(
            "INSERT INTO agents (id, name, email) VALUES (%s, %s, %s)",
            (agent_id, "OAuth", f"oauth_{agent_id.hex[:8]}@test.com"),
        )
    return agent_id


def test_social_identity_constraints_and_last_login_are_persisted(social_db):
    agent_id = _agent(social_db)
    now = datetime.now(timezone.utc)
    identity = SocialIdentity(uuid4(), agent_id, "GOOGLE", "subject", "oauth@test.com", now, now)
    with PostgresUnitOfWork(social_db) as uow:
        assert uow.social_identities.save(identity)
        assert uow.social_identities.touch_last_login(identity.id, now + timedelta(seconds=1))
    with PostgresUnitOfWork(social_db) as uow:
        stored = uow.social_identities.get_by_provider_subject("GOOGLE", "subject")
        assert stored is not None and stored.last_login_at == now + timedelta(seconds=1)
        assert uow.social_identities.list_by_agent(agent_id) == [stored]

    with social_db.get_connection(autocommit=True) as conn:
        with pytest.raises(psycopg.IntegrityError):
            conn.execute(
                "INSERT INTO social_identities (id, agent_id, provider, provider_subject, email_at_link, created_at, last_login_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (uuid4(), agent_id, "GOOGLE", "subject", "other@test.com", now, now),
            )
        with pytest.raises(psycopg.IntegrityError):
            conn.execute(
                "INSERT INTO social_identities (id, agent_id, provider, provider_subject, email_at_link, created_at, last_login_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (uuid4(), agent_id, "GOOGLE", "other", "other@test.com", now, now),
            )


def test_matching_oauth_challenge_is_consumed_once(social_db):
    now = datetime.now(timezone.utc)
    challenge = AuthChallenge(
        "challenge", None, "OAUTH_LOGIN", 0, now + timedelta(minutes=5), None, now,
        provider="GOOGLE", state_hash="state", pkce_verifier="verifier", return_path="/home",
    )
    with PostgresUnitOfWork(social_db) as uow:
        uow.challenges.save(challenge)
    barrier = threading.Barrier(2)

    def consume():
        barrier.wait(timeout=10)
        with PostgresUnitOfWork(social_db) as uow:
            return uow.challenges.consume_oauth("challenge", "GOOGLE", "state", now)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: consume(), range(2)))
    assert sum(result is not None for result in results) == 1

    with social_db.get_connection(autocommit=True) as conn:
        columns = {row["column_name"] for row in conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'auth_challenges'"
        ).fetchall()}
    assert {"code", "access_token", "refresh_token"}.isdisjoint(columns)
