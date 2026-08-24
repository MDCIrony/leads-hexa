import uuid

from application.dtos.commands import IngestLeadCommand
from application.use_cases.ingest_lead_use_case import IngestLeadUseCase, payload_of
from domain.entities.intake_record import IntakeRecord
from domain.entities.lead_source import LeadSource
from domain.events.lead_events import LeadDisqualified
from domain.value_objects.enums import LeadSourceKind
from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
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


def _seed_source(conn, tenant_id: uuid.UUID) -> uuid.UUID:
    """intake_records.tenant_id and .source_id are real foreign keys
    (migration 005): a full ingestion needs a persisted organization and
    source, unlike outbox_events itself."""
    conn.execute(
        "INSERT INTO tenants (id, name, slug, created_at) VALUES (%s, %s, %s, now())",
        (tenant_id, "Acme", f"acme-{tenant_id}"),
    )
    source = RawSqlLeadSourceRepository(conn).save(
        LeadSource.create(tenant_id=tenant_id, name="Formulario", kind=LeadSourceKind.MANUAL_FORM)
    )
    return source.id.value


def test_record_and_list_unpublished_round_trips_the_payload(test_db):
    repo, conn, ctx = _repo(test_db)
    try:
        event = _event()
        repo.record(event)

        entries = repo.list_unpublished(10)

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

        assert repo.list_unpublished(10) == []
    finally:
        ctx.__exit__(None, None, None)


def test_mark_failed_keeps_it_in_the_unpublished_list(test_db):
    repo, conn, ctx = _repo(test_db)
    try:
        event = _event()
        repo.record(event)

        repo.mark_failed(event.event_id, "connection refused")

        entries = repo.list_unpublished(10)
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
        assert repo.list_unpublished(10) == []
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

    result = IngestLeadUseCase(uow=PostgresUnitOfWork(test_db)).execute(command, existing_record=existing)

    repo, conn, ctx = _repo(test_db)
    try:
        entries = repo.list_unpublished(10)
        assert len(entries) == 1
        assert entries[0].partition_key == result.lead_id
        assert entries[0].tenant_id == str(tenant_id)
        assert entries[0].payload["lead_id"] == result.lead_id
    finally:
        ctx.__exit__(None, None, None)
