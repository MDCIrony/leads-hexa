from datetime import datetime, timedelta, timezone
from uuid import uuid4

from domain.agents.agent import Agent
from domain.sessions.auth_session import AuthSession


def test_a_session_is_active_until_it_expires_or_is_revoked(uow_factory):
    now = datetime.now(timezone.utc)
    with uow_factory() as uow:
        agent_id = uow.agents.save(Agent.create("S", f"s_{uuid4().hex[:8]}@test.com")).id.value
        live = AuthSession("live", agent_id, now, now + timedelta(hours=1))
        uow.sessions.save(live)
        uow.sessions.save(AuthSession("old", agent_id, now - timedelta(hours=2), now - timedelta(hours=1)))

    with uow_factory() as uow:
        assert uow.sessions.get_active("live", now) == live
        assert uow.sessions.get_active("old", now) is None
        assert uow.sessions.get_active("missing", now) is None
        uow.sessions.revoke("live", now)
        assert uow.sessions.get_active("live", now) is None
