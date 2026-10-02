from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from domain.agents.agent import Agent
from domain.exceptions import DomainException
from domain.sessions.auth_session import AuthSession


@pytest.mark.parametrize("statement,params,error_code", [
    ("INSERT INTO agents (id, name, email) VALUES (%s, NULL, 'x@test.com')", (uuid4(),), "MISSING_REQUIRED_FIELD"),
    ("INSERT INTO auth_sessions (token_hash, agent_id, created_at, expires_at) VALUES ('t', %s, now(), now())",
     (uuid4(),), "RELATED_ENTITY_NOT_FOUND"),
])
def test_a_constraint_the_use_case_could_not_precheck_surfaces_as_a_domain_error(
    uow_factory, statement, params, error_code
):
    with pytest.raises(DomainException) as raised:
        with uow_factory() as uow:
            uow.connection.execute(statement, params)

    assert raised.value.error_code == error_code


def test_a_duplicate_email_surfaces_as_already_exists(uow_factory):
    with uow_factory() as uow:
        uow.agents.save(Agent.create("A", "dup@test.com"))

    with pytest.raises(DomainException) as raised:
        with uow_factory() as uow:
            uow.agents.save(Agent.create("B", "DUP@test.com"))

    assert raised.value.error_code == "ALREADY_EXISTS"


def test_an_error_inside_the_block_rolls_everything_back(uow_factory):
    agent = Agent.create("A", "a@test.com")
    with pytest.raises(RuntimeError):
        with uow_factory() as uow:
            uow.agents.save(agent)
            raise RuntimeError("boom")

    with uow_factory() as uow:
        assert uow.agents.get_by_id(agent.id.value) is None


def test_one_instance_runs_one_transaction_per_block(uow_factory):
    """Use cases hold one unit of work and enter it once per step."""
    uow = uow_factory()
    now = datetime.now(timezone.utc)
    with uow:
        agent_id = uow.agents.save(Agent.create("A", "a@test.com")).id.value
    with uow:
        uow.sessions.save(AuthSession("s", agent_id, now, now + timedelta(hours=1)))

    with uow_factory() as other:
        assert other.sessions.get_active("s", now) is not None
    assert uow.connection is None
