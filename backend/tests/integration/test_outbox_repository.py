import uuid

import pytest

from application.dtos.commands import IngestLeadCommand
from application.use_cases.ingest_lead_use_case import IngestLeadUseCase
from infrastructure.adapters.output.admissions.in_process_lead_admission import InProcessLeadAdmission
from application.use_cases.intake.payloads import payload_of
from domain.entities.intake_record import IntakeRecord
from domain.entities.lead_source import LeadSource
from domain.events.lead_events import LeadDisqualified
from domain.value_objects.enums import LeadSourceKind
from chassis.web import request_id_var
from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
from infrastructure.adapters.output.persistence.raw_sql_intake_record_repository import (
    RawSqlIntakeRecordRepository,
)
from infrastructure.adapters.output.persistence.raw_sql_lead_source_repository import (
    RawSqlLeadSourceRepository,
)
from infrastructure.adapters.output.persistence.raw_sql_outbox_repository import RawSqlOutboxRepository


def _repo(test_db):
    ctx = test_db.get_connection(autocommit=True)
    conn = ctx.__enter__()
    return RawSqlOutboxRepository(conn), conn, ctx


def _event() -> LeadDisqualified:
    # outbox_events.tenant_id carries no foreign key (migration 009): the
    # row is delivery mechanics, not a fact scoped to a live organization.
    return LeadDisqualified(
        tenant_id=str(uuid.uuid4()),
        lead_id=str(uuid.uuid4()),
        source_id=str(uuid.uuid4()),
        reason="Sin forma de contactar",
    )


def _event_for(lead_id: str) -> LeadDisqualified:
    return LeadDisqualified(
        tenant_id=str(uuid.uuid4()),
        lead_id=lead_id,
        source_id=str(uuid.uuid4()),
        reason="Sin forma de contactar",
    )


def _seed_source(conn, tenant_id: uuid.UUID) -> uuid.UUID:
    """intake_records.source_id is a real foreign key (migration 005): a full
    ingestion needs a persisted source, unlike outbox_events itself."""
    source = RawSqlLeadSourceRepository(conn).save(
        LeadSource.create(tenant_id=tenant_id, name="Formulario", kind=LeadSourceKind.MANUAL_FORM)
    )
    return source.id.value


def test_record_and_list_unpublished_round_trips_the_payload(test_db):
    repo, conn, ctx = _repo(test_db)
    try:
        event = _event()
        repo.record(event)

        entries = repo.list_unpublished("product", 10)

        assert [entry.id for entry in entries] == [event.event_id]
        entry = entries[0]
        assert entry.tenant_id == event.tenant_id
        assert entry.partition_key == event.lead_id
        assert entry.event_type == "LeadDisqualified"
        assert entry.payload["reason"] == "Sin forma de contactar"
        assert entry.payload["lead_id"] == event.lead_id
    finally:
        ctx.__exit__(None, None, None)


def test_mark_published_removes_it_from_the_unpublished_list(test_db):
    repo, conn, ctx = _repo(test_db)
    try:
        event = _event()
        repo.record(event)

        repo.mark_published(event.event_id)

        assert repo.list_unpublished("product", 10) == []
    finally:
        ctx.__exit__(None, None, None)


def test_mark_failed_keeps_it_in_the_unpublished_list(test_db):
    repo, conn, ctx = _repo(test_db)
    try:
        event = _event()
        repo.record(event)

        repo.mark_failed(event.event_id, "connection refused")

        entries = repo.list_unpublished("product", 10)
        assert [entry.id for entry in entries] == [event.event_id]
    finally:
        ctx.__exit__(None, None, None)


def test_a_rolled_back_record_leaves_no_row(test_db):
    """The whole point of the outbox: the INSERT lives inside the caller's
    transaction, so a rollback takes it with it instead of leaving an
    outbound fact for a lead that was never saved."""
    uow = PostgresUnitOfWork(test_db)
    event = _event()

    try:
        with uow:
            uow.outbox.record(event)
            raise RuntimeError("boom")
    except RuntimeError:
        pass

    repo, conn, ctx = _repo(test_db)
    try:
        assert repo.list_unpublished("product", 10) == []
    finally:
        ctx.__exit__(None, None, None)


def test_a_full_ingestion_leaves_exactly_one_unpublished_entry(test_db):
    tenant_id = uuid.uuid4()
    with test_db.get_connection(autocommit=True) as conn:
        source_id = _seed_source(conn, tenant_id)

    command = IngestLeadCommand(
        tenant_id=tenant_id,
        source_id=source_id,
        first_name="Ana",
        last_name="Diaz",
        email="ana@x.test",
        phone=None,
        company="Acme",
        budget=1000.0,
        industry="tech",
        custom_attributes={},
    )
    existing = IntakeRecord.create(tenant_id=tenant_id, source_id=source_id, payload=payload_of(command))
    # Persisted before the call, as the real pipeline does: the use case claims
    # its record with a locking read, which a row that only exists in memory
    # cannot answer.
    with test_db.get_connection(autocommit=True) as conn:
        RawSqlIntakeRecordRepository(conn).save(existing)

    admission = InProcessLeadAdmission(lambda: PostgresUnitOfWork(test_db))
    result = IngestLeadUseCase(uow=PostgresUnitOfWork(test_db), admission=admission).execute(
        command, existing_record=existing)

    repo, conn, ctx = _repo(test_db)
    try:
        entries = repo.list_unpublished("product", 10)
        assert len(entries) == 1
        assert entries[0].partition_key == result.lead_id
        assert entries[0].tenant_id == str(tenant_id)
        assert entries[0].payload["lead_id"] == result.lead_id
    finally:
        ctx.__exit__(None, None, None)


def test_a_repeatedly_failing_entry_is_never_dropped_and_never_starves_the_rest(test_db):
    """A broker down for a few seconds must not cost a lead. The entry that
    keeps failing sinks in the order so newer ones overtake it, but it stays
    in the batch — this table exists so nothing gets lost."""
    repo, _, ctx = _repo(test_db)
    try:
        stubborn = _event()
        repo.record(stubborn)
        for attempt in range(25):
            repo.mark_failed(stubborn.event_id, f"broker unreachable (attempt {attempt})")

        # Well past any cap a retry limit would have imposed.
        assert [entry.id for entry in repo.list_unpublished("product", 10)] == [stubborn.event_id]

        fresh = _event()
        repo.record(fresh)

        # The newcomer goes first: the failing one no longer holds the batch.
        assert [entry.id for entry in repo.list_unpublished("product", 10)] == [fresh.event_id, stubborn.event_id]
    finally:
        ctx.__exit__(None, None, None)


def test_an_event_goes_out_only_through_its_own_channel(test_db):
    repo, _, ctx = _repo(test_db)
    try:
        event = _event()
        repo.record(event, channel="internal")

        assert [entry.id for entry in repo.list_unpublished("internal", 10)] == [event.event_id]
        assert repo.list_unpublished("product", 10) == []
        assert repo.list_unpublished("job", 10) == []
        assert repo.list_unpublished("internal", 10)[0].channel == "internal"
    finally:
        ctx.__exit__(None, None, None)


def test_the_default_channel_is_product(test_db):
    repo, _, ctx = _repo(test_db)
    try:
        repo.record(_event())

        assert repo.list_unpublished("product", 10)[0].channel == "product"
    finally:
        ctx.__exit__(None, None, None)


def test_an_unknown_channel_is_rejected_by_the_database(test_db):
    repo, _, ctx = _repo(test_db)
    try:
        with pytest.raises(Exception):
            repo.record(_event(), channel="carrier-pigeon")
    finally:
        ctx.__exit__(None, None, None)


def test_correlation_id_comes_from_the_current_request(test_db):
    repo, _, ctx = _repo(test_db)
    token = request_id_var.set("rid-1")
    try:
        event = _event()
        repo.record(event)

        assert repo.list_unpublished("product", 10)[0].correlation_id == "rid-1"
    finally:
        request_id_var.reset(token)
        ctx.__exit__(None, None, None)


def test_correlation_id_is_none_outside_a_request(test_db):
    repo, _, ctx = _repo(test_db)
    try:
        repo.record(_event())

        # The ContextVar default "-" means "no request"; it is stored as NULL.
        assert repo.list_unpublished("product", 10)[0].correlation_id is None
    finally:
        ctx.__exit__(None, None, None)


def test_an_event_without_a_tenant_is_stored(test_db):
    repo, _, ctx = _repo(test_db)
    try:
        event = _event()
        object.__setattr__(event, "tenant_id", None)
        repo.record(event, channel="internal")

        entries = repo.list_unpublished("internal", 10)
        assert [entry.id for entry in entries] == [event.event_id]
        assert entries[0].tenant_id is None
    finally:
        ctx.__exit__(None, None, None)


def test_only_the_oldest_unpublished_row_of_a_key_is_eligible(test_db):
    """On a compacted topic the last record per key wins: v6 must never leave
    before a failing v5. The newer row is not even fetched, so a relay pass
    that delivers sequentially cannot let it out after r1 fails."""
    repo, _, ctx = _repo(test_db)
    try:
        lead_id = str(uuid.uuid4())
        first, second = _event_for(lead_id), _event_for(lead_id)
        other = _event()
        repo.record(first)
        repo.record(second)
        repo.record(other)

        assert [e.id for e in repo.list_unpublished("product", 10)] == [first.event_id, other.event_id]

        repo.mark_failed(first.event_id, "broker unreachable")

        # The failed row sinks behind other keys but still holds back its successor.
        for _ in range(2):
            ids = [e.id for e in repo.list_unpublished("product", 10)]
            assert ids == [other.event_id, first.event_id]
            assert second.event_id not in ids

        repo.mark_published(first.event_id)

        assert [e.id for e in repo.list_unpublished("product", 10)] == [second.event_id, other.event_id]
    finally:
        ctx.__exit__(None, None, None)
