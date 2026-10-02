from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg
import pytest

from domain.agents.agent import Agent
from domain.social.social_identity import SocialIdentity


@pytest.fixture
def agent_id(uow_factory):
    with uow_factory() as uow:
        return uow.agents.save(Agent.create("OAuth", f"oauth_{uuid4().hex[:8]}@test.com")).id.value


def _identity(agent_id, provider="GOOGLE", subject="subject", now=None):
    now = now or datetime.now(timezone.utc)
    return SocialIdentity(uuid4(), agent_id, provider, subject, "oauth@test.com", now, now)


def test_a_link_round_trips_and_records_the_last_login(uow_factory, agent_id):
    identity = _identity(agent_id)
    later = identity.created_at + timedelta(seconds=1)
    with uow_factory() as uow:
        assert uow.social_identities.save(identity) is True
        assert uow.social_identities.touch_last_login(identity.id, later) is True
        assert uow.social_identities.touch_last_login(uuid4(), later) is False

    with uow_factory() as uow:
        stored = uow.social_identities.get_by_provider_subject("GOOGLE", "subject")
        assert stored.last_login_at == later
        assert uow.social_identities.list_by_agent(agent_id) == [stored]
        assert uow.social_identities.get_by_provider_subject("GITHUB", "subject") is None


def test_a_taken_subject_or_a_second_link_to_the_same_provider_answers_false(uow_factory, agent_id):
    with uow_factory() as uow:
        assert uow.social_identities.save(_identity(agent_id))
        other_agent = uow.agents.save(Agent.create("Other", "other@test.com")).id.value

        assert uow.social_identities.save(_identity(other_agent)) is False
        assert uow.social_identities.save(_identity(agent_id, subject="another")) is False
        assert uow.social_identities.save(_identity(agent_id, provider="GITHUB", subject="gh")) is True
        assert [i.provider for i in uow.social_identities.list_by_agent(agent_id)] == ["GITHUB", "GOOGLE"]


def test_the_constraints_hold_for_a_writer_that_bypasses_the_repository(test_db, agent_id):
    now = datetime.now(timezone.utc)
    insert = (
        "INSERT INTO social_identities (id, agent_id, provider, provider_subject, email_at_link, created_at, last_login_at)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s)"
    )
    with test_db.get_connection(autocommit=True) as conn:
        conn.execute(insert, (uuid4(), agent_id, "GOOGLE", "subject", "a@test.com", now, now))
        for provider, subject in (("GOOGLE", "subject"), ("GOOGLE", "other"), ("FACEBOOK", "x"), ("GITHUB", " ")):
            with pytest.raises(psycopg.IntegrityError):
                conn.execute(insert, (uuid4(), agent_id, provider, subject, "b@test.com", now, now))


def test_no_provider_token_is_ever_stored(test_db):
    with test_db.get_connection(autocommit=True) as conn:
        columns = {row["column_name"] for row in conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name IN ('auth_challenges', 'social_identities')"
        ).fetchall()}
    assert {"code", "access_token", "refresh_token"}.isdisjoint(columns)
