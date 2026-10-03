import json
import uuid
from dataclasses import dataclass

from chassis.outbox import OutboxRow

from domain.events.internal_event import InternalEvent
from domain.events.lead_events import LeadAssigned, LeadDisqualified
from infrastructure.adapters.output.persistence.outbox.outbox_store import open_outbox_store
from infrastructure.adapters.output.persistence.unit_of_work import PostgresUnitOfWork


def _product_event() -> LeadDisqualified:
    return LeadDisqualified(
        tenant_id=str(uuid.uuid4()), lead_id=str(uuid.uuid4()),
        source_id=str(uuid.uuid4()), reason="No contact channel",
    )


def _internal_event() -> LeadAssigned:
    return LeadAssigned(tenant_id=str(uuid.uuid4()), lead_id=str(uuid.uuid4()), agent_id=str(uuid.uuid4()))


@dataclass(kw_only=True)
class _TenantlessState(InternalEvent):
    """The channel admits state that belongs to no organization."""

    subject_id: str

    @property
    def partition_key(self) -> str:
        return self.subject_id


def _record(test_db, event, channel: str) -> None:
    with PostgresUnitOfWork(test_db) as uow:
        uow.outbox.record(event, channel=channel)


def test_fetch_returns_only_the_requested_channel(test_db):
    product, internal = _product_event(), _internal_event()
    _record(test_db, product, "product")
    _record(test_db, internal, "internal")

    with open_outbox_store(test_db) as store:
        rows = store.fetch("internal", 10)

    assert [row.id for row in rows] == [internal.event_id]
    assert rows[0].channel == "internal"


def test_a_row_carries_what_the_chassis_dispatchers_need(test_db):
    event = _internal_event()
    _record(test_db, event, "internal")

    with open_outbox_store(test_db) as store:
        (row,) = store.fetch("internal", 10)

    assert isinstance(row, OutboxRow)
    assert row.tenant_id == event.tenant_id and isinstance(row.tenant_id, str)
    assert row.partition_key == event.lead_id
    assert row.event_type == "LeadAssigned"
    # timezone-aware, or the envelope's occurred_at would carry no offset.
    assert row.occurred_on.utcoffset() is not None
    assert row.occurred_on == event.occurred_on
    assert row.correlation_id is None
    assert json.loads(json.dumps(row.payload)) == row.payload == event.as_payload()


def test_a_tenantless_row_has_a_none_tenant_id(test_db):
    event = _TenantlessState(tenant_id=None, subject_id=str(uuid.uuid4()))
    _record(test_db, event, "internal")

    with open_outbox_store(test_db) as store:
        (row,) = store.fetch("internal", 10)

    assert row.tenant_id is None


def test_marks_persist_after_the_store_closes(test_db):
    published, failed = _internal_event(), _internal_event()
    _record(test_db, published, "internal")
    _record(test_db, failed, "internal")

    with open_outbox_store(test_db) as store:
        store.mark_published(published.event_id)
        store.mark_failed(failed.event_id, "broker down")

    with open_outbox_store(test_db) as store:
        rows = store.fetch("internal", 10)
    assert [row.id for row in rows] == [failed.event_id]

    with test_db.get_connection(autocommit=True) as conn:
        attempts, error = conn.execute(
            "SELECT attempts, last_error FROM outbox_events WHERE id = %s", (failed.event_id,)
        ).fetchone().values()
    assert (attempts, error) == (1, "broker down")


def test_fetch_honours_the_limit(test_db):
    for _ in range(3):
        _record(test_db, _internal_event(), "internal")

    with open_outbox_store(test_db) as store:
        assert len(store.fetch("internal", 2)) == 2
