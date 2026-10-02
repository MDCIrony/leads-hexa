from datetime import datetime, timedelta, timezone

import pytest
from chassis.web import request_id_var

from domain.events.identity_events import TenantState
from domain.tenants.tenant import Tenant
from infrastructure.adapters.output.persistence.outbox_store import open_outbox_store

_BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _record(uow_factory, tenant=None, seconds=0):
    tenant = tenant or Tenant.create(name="Acme")
    event = TenantState.of(tenant)
    event.occurred_on = _BASE + timedelta(seconds=seconds)
    with uow_factory() as uow:
        uow.outbox.record(event)
    return event


def _fetch(test_db, channel="internal", limit=10):
    with open_outbox_store(test_db) as store:
        return store.fetch(channel, limit)


def test_fetch_returns_the_row_with_its_envelope_fields(test_db, uow_factory):
    tenant = Tenant.create(name="Acme")
    token = request_id_var.set("req-9")
    try:
        event = _record(uow_factory, tenant)
    finally:
        request_id_var.reset(token)

    [row] = _fetch(test_db)

    assert (row.id, row.channel, row.event_type, row.partition_key) == (
        event.event_id, "internal", "TenantState", str(tenant.id),
    )
    assert row.tenant_id == str(tenant.id)
    assert row.payload == event.as_payload()
    assert row.correlation_id == "req-9"
    assert row.occurred_on == event.occurred_on


def test_mark_published_removes_the_row_from_the_backlog(test_db, uow_factory):
    event = _record(uow_factory)

    with open_outbox_store(test_db) as store:
        store.mark_published(event.event_id)

    assert _fetch(test_db) == []


def test_mark_failed_keeps_the_row_and_counts_the_attempt(test_db, uow_factory):
    event = _record(uow_factory)

    with open_outbox_store(test_db) as store:
        store.mark_failed(event.event_id, "broker unreachable")

    assert [row.id for row in _fetch(test_db)] == [event.event_id]
    with uow_factory() as uow:
        stored = uow.connection.execute("SELECT attempts, last_error FROM outbox_events").fetchone()
    assert (stored["attempts"], stored["last_error"]) == (1, "broker unreachable")


def test_a_failing_row_sinks_behind_fresh_ones_and_is_never_dropped(test_db, uow_factory):
    stubborn = _record(uow_factory, seconds=0)
    fresh = _record(uow_factory, seconds=1)
    with open_outbox_store(test_db) as store:
        for _ in range(20):
            store.mark_failed(stubborn.event_id, "broker unreachable")

    assert [row.id for row in _fetch(test_db)] == [fresh.event_id, stubborn.event_id]


def test_only_the_oldest_unpublished_row_of_a_key_is_eligible(test_db, uow_factory):
    tenant = Tenant.create(name="Acme")
    first = _record(uow_factory, tenant, seconds=0)
    second = _record(uow_factory, tenant, seconds=1)
    other = _record(uow_factory, seconds=2)

    assert [row.id for row in _fetch(test_db)] == [first.event_id, other.event_id]

    with open_outbox_store(test_db) as store:
        store.mark_failed(first.event_id, "broker unreachable")
    # The poison row blocks its own key and nothing else.
    assert [row.id for row in _fetch(test_db)] == [other.event_id, first.event_id]

    with open_outbox_store(test_db) as store:
        store.mark_published(first.event_id)
    assert [row.id for row in _fetch(test_db)] == [second.event_id, other.event_id]


def test_the_limit_caps_the_batch(test_db, uow_factory):
    for seconds in range(3):
        _record(uow_factory, seconds=seconds)

    assert len(_fetch(test_db, limit=2)) == 2


def test_another_channel_is_empty(test_db, uow_factory):
    _record(uow_factory)

    assert _fetch(test_db, channel="product") == []


def test_the_marks_survive_an_error_only_if_the_block_completes(test_db, uow_factory):
    event = _record(uow_factory)

    with pytest.raises(RuntimeError):
        with open_outbox_store(test_db) as store:
            store.mark_published(event.event_id)
            raise RuntimeError("boom")

    assert [row.id for row in _fetch(test_db)] == [event.event_id]
