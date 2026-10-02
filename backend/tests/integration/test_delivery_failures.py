"""What the delivery chain promises when a hop fails: a relay that dies after
delivering re-delivers and publishes once. Real database, doubles for the brokers."""
from contextlib import contextmanager
from uuid import uuid4

import pytest
from chassis.outbox import OutboxRelay

from domain.events.lead_events import LeadAssigned
from infrastructure.adapters.output.persistence.outbox_store import open_outbox_store
from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork


def _count(test_db, sql: str, params: tuple = ()) -> int:
    with test_db.get_connection(autocommit=True) as conn:
        return conn.execute(sql, params).fetchone()["n"]


def _seed_assigned_event(test_db) -> LeadAssigned:
    """A LeadAssigned in the internal channel; the relay reads only the outbox row."""
    with PostgresUnitOfWork(test_db) as uow:
        event = LeadAssigned(tenant_id=str(uuid4()), lead_id=str(uuid4()), agent_id=str(uuid4()))
        uow.outbox.record(event, channel="internal")
    return event


class _CapturingDispatcher:
    def __init__(self) -> None:
        self.delivered = []

    def dispatch(self, row) -> None:
        self.delivered.append(row)


class _MarkDiesStore:
    """The real store, except that recording the outcome fails: the relay
    delivered and then died before it could say so."""

    def __init__(self, store) -> None:
        self._store = store

    def fetch(self, channel, limit):
        return self._store.fetch(channel, limit)

    def mark_published(self, row_id):
        raise RuntimeError("relay died after delivering")

    def mark_failed(self, row_id, error):
        self._store.mark_failed(row_id, error)


def test_a_row_delivered_twice_after_a_relay_crash_is_published_once(test_db):
    event = _seed_assigned_event(test_db)
    dispatcher = _CapturingDispatcher()

    @contextmanager
    def dying_store():
        with open_outbox_store(test_db) as store:
            yield _MarkDiesStore(store)

    with pytest.raises(RuntimeError, match="relay died"):
        OutboxRelay(dying_store, {"internal": [dispatcher]}).drain("internal")
    # The next pass, on a healthy relay, finds the row unmarked and delivers it again.
    assert OutboxRelay(lambda: open_outbox_store(test_db), {"internal": [dispatcher]}).drain("internal") == 1

    assert [row.id for row in dispatcher.delivered] == [event.event_id, event.event_id]

    assert _count(test_db, "SELECT COUNT(*) AS n FROM outbox_events WHERE published_at IS NOT NULL") == 1
