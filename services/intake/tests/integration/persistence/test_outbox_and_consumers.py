from datetime import datetime, timezone
from uuid import uuid4

import pytest
from chassis.outbox import envelope
from chassis.testing.contracts import assert_conforms
from chassis.web import request_id_var

from domain.events.intake_events import IntakeJobRequested, IntakeRejected
from infrastructure.adapters.output.persistence.outbox_repository import PostgresOutboxRepository
from infrastructure.adapters.output.persistence.outbox_store import PostgresOutboxStore
from infrastructure.adapters.output.persistence.processed_event_repository import PostgresProcessedEventRepository
from infrastructure.adapters.output.persistence.provisioned_tenant_repository import (
    PostgresProvisionedTenantRepository,
)


def _rejected(record_id=None) -> IntakeRejected:
    return IntakeRejected(tenant_id=str(uuid4()), intake_record_id=record_id or str(uuid4()), reason="Invalid email")


def test_an_intake_rejected_row_becomes_an_envelope_that_conforms_to_its_schema(conn):
    event = _rejected()
    reset = request_id_var.set("req-7")
    try:
        PostgresOutboxRepository(conn).record(event, channel="internal")
    finally:
        request_id_var.reset(reset)

    [row] = PostgresOutboxStore(conn).fetch("internal", 10)

    assert (row.event_type, row.partition_key, row.tenant_id, row.correlation_id) == (
        "IntakeRejected", event.intake_record_id, event.tenant_id, "req-7")
    assert_conforms(envelope(row, "intake"), "events/IntakeRejected.v1.schema.json")


def test_a_job_row_travels_on_its_own_channel(conn):
    event = IntakeJobRequested(tenant_id=str(uuid4()), job_id=str(uuid4()))
    repo = PostgresOutboxRepository(conn)
    repo.record(event, channel="job")
    repo.record(_rejected(), channel="internal")
    store = PostgresOutboxStore(conn)

    [job] = store.fetch("job", 10)

    assert (job.channel, job.payload) == ("job", {"tenant_id": event.tenant_id, "job_id": event.job_id})
    assert [r.event_type for r in store.fetch("internal", 10)] == ["IntakeRejected"]


def test_a_row_waits_for_the_older_unpublished_row_of_its_key(conn):
    repo, store, key = PostgresOutboxRepository(conn), PostgresOutboxStore(conn), str(uuid4())
    older, newer = _rejected(key), _rejected(key)
    older.occurred_on = datetime(2026, 1, 1, tzinfo=timezone.utc)
    newer.occurred_on = datetime(2026, 1, 2, tzinfo=timezone.utc)
    repo.record(newer)
    repo.record(older)

    assert [r.id for r in store.fetch("internal", 10)] == [older.event_id]
    store.mark_published(older.event_id)
    assert [r.id for r in store.fetch("internal", 10)] == [newer.event_id]


def test_a_failed_row_is_kept_with_its_error_and_sinks_behind_fresh_ones(conn):
    repo, store = PostgresOutboxRepository(conn), PostgresOutboxStore(conn)
    failing, fresh = _rejected(), _rejected()
    failing.occurred_on = datetime(2026, 1, 1, tzinfo=timezone.utc)
    repo.record(failing)
    repo.record(fresh)

    store.mark_failed(failing.event_id, "broker down")

    assert [r.id for r in store.fetch("internal", 10)] == [fresh.event_id, failing.event_id]
    row = conn.execute("SELECT attempts, last_error FROM outbox_events WHERE id = %s", (failing.event_id,)).fetchone()
    assert (row["attempts"], row["last_error"]) == (1, "broker down")


def test_the_outbox_refuses_a_channel_it_does_not_know(conn):
    import psycopg

    with pytest.raises(psycopg.errors.CheckViolation):
        PostgresOutboxRepository(conn).record(_rejected(), channel="product")


def test_a_processed_event_is_marked_once_per_consumer(conn):
    repo, event_id = PostgresProcessedEventRepository(conn), uuid4()

    assert [repo.mark("a", event_id), repo.mark("a", event_id), repo.mark("b", event_id)] == [True, False, True]


def test_a_tenant_is_marked_provisioned_once(conn):
    repo, tenant_id = PostgresProvisionedTenantRepository(conn), uuid4()

    assert [repo.mark(tenant_id), repo.mark(tenant_id)] == [True, False]
