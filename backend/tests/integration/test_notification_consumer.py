import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from chassis.consumer import Envelope
from chassis.outbox import OutboxRow, envelope

from application.handlers.notification_handler import NotificationHandler
from domain.entities.agent import Agent
from domain.entities.tenant import Tenant
from domain.value_objects.enums import AgentRole
from infrastructure.adapters.input.events.notification_consumer import NotificationConsumer
from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork

_GROUP = "notifications.lead-events"


def _seed_agent(test_db) -> Agent:
    # notifications has foreign keys to tenants and agents (migration 008).
    with PostgresUnitOfWork(test_db) as uow:
        tenant = uow.tenants.save(Tenant.create(name=f"Org {uuid4()}"))
        return uow.agents.save(
            Agent.create("Ana", f"{uuid4()}@test.com", role=AgentRole.AGENT, tenant_id=tenant.id.value)
        )


def _lead_assigned(agent: Agent) -> Envelope:
    """Built the way the relay builds it, then read back from bytes the way
    a Kafka consumer reads it."""
    row = OutboxRow(
        id=uuid4(), channel="internal", tenant_id=str(agent.tenant_id.value), partition_key=str(uuid4()),
        event_type="LeadAssigned", payload={"lead_id": str(uuid4()), "agent_id": str(agent.id)},
        occurred_on=datetime.now(timezone.utc), correlation_id=None,
    )
    return Envelope.from_bytes(json.dumps(envelope(row, "lead-core")).encode())


def _count(test_db, sql: str, params: tuple) -> int:
    with test_db.get_connection(autocommit=True) as conn:
        return conn.execute(sql, params).fetchone()["n"]


def test_the_same_envelope_twice_creates_one_notification(test_db):
    agent = _seed_agent(test_db)
    message = _lead_assigned(agent)
    consumer = NotificationConsumer(lambda: PostgresUnitOfWork(test_db), _GROUP)

    consumer(message)
    consumer(message)

    assert _count(test_db, "SELECT COUNT(*) AS n FROM notifications WHERE recipient_id = %s",
                  (agent.id.value,)) == 1


def test_a_failing_effect_leaves_no_processed_row(test_db, monkeypatch):
    """The mark and the effect share one transaction: if the effect could fail
    after the mark committed, the retry would see the event as done and the
    notification would be lost for good."""
    agent = _seed_agent(test_db)
    message = _lead_assigned(agent)

    def _boom(self, *args):
        raise RuntimeError("effect failed")

    monkeypatch.setattr(NotificationHandler, "apply", _boom)
    with pytest.raises(RuntimeError):
        NotificationConsumer(lambda: PostgresUnitOfWork(test_db), _GROUP)(message)

    assert _count(test_db, "SELECT COUNT(*) AS n FROM processed_events WHERE event_id = %s",
                  (message.event_id,)) == 0
