from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from domain.records.intake_record import IntakeError, IntakeRecord
from domain.value_objects.enums import IntakeRecordStatus
from infrastructure.adapters.output.persistence.intake_record_repository import PostgresIntakeRecordRepository
from tests.integration.persistence.helpers import seed_job, seed_source

_OPEN = (IntakeRecordStatus.PENDING, IntakeRecordStatus.REJECTED)


def _record(source, **fields) -> IntakeRecord:
    return IntakeRecord.create(
        tenant_id=source.tenant_id.value, source_id=source.id.value, payload=fields.pop("payload", {}), **fields)


def _rejected(source, *errors):
    record = _record(source, payload={"email": "bad"})
    record.reject(list(errors) or [IntakeError(field="email", message="Invalid format")])
    return record


def test_two_errors_read_back_with_every_field(conn):
    repo, source = PostgresIntakeRecordRepository(conn), seed_source(conn)
    record = repo.save(_rejected(
        source,
        IntakeError(field="email", message="Invalid format", received_value="bad", error_code="INVALID_EMAIL"),
        IntakeError(field="phone", message="Missing"),
    ))

    found = repo.get_by_id_and_tenant(record.id.value, source.tenant_id.value)

    assert found.status == IntakeRecordStatus.REJECTED
    assert {(e.field, e.message, e.received_value, e.error_code) for e in found.errors} == {
        ("email", "Invalid format", "bad", "INVALID_EMAIL"), ("phone", "Missing", None, None)}


def test_saving_again_with_fewer_errors_replaces_the_previous_set(conn):
    repo, source = PostgresIntakeRecordRepository(conn), seed_source(conn)
    record = repo.save(_rejected(source, IntakeError("email", "Invalid"), IntakeError("phone", "Missing")))
    record.reject([IntakeError(field="email", message="Still invalid")])
    repo.save(record)

    found = repo.get_by_id_and_tenant(record.id.value, source.tenant_id.value)

    assert [(e.field, e.message) for e in found.errors] == [("email", "Still invalid")]


def test_each_record_of_a_page_gets_only_its_own_errors(conn):
    repo, source = PostgresIntakeRecordRepository(conn), seed_source(conn)
    first = repo.save(_rejected(source, IntakeError("email", "one")))
    second = repo.save(_rejected(source, IntakeError("phone", "two"), IntakeError("budget", "three")))
    clean = repo.save(_record(source))

    page = {r.id.value: r for r in repo.list_by_tenant(source.tenant_id.value)}

    assert [e.message for e in page[first.id.value].errors] == ["one"]
    assert {e.message for e in page[second.id.value].errors} == {"two", "three"}
    assert page[clean.id.value].errors == []


def test_a_record_of_another_organization_reads_back_as_missing(conn):
    repo, source = PostgresIntakeRecordRepository(conn), seed_source(conn)
    record = repo.save(_record(source))

    assert repo.get_by_id_and_tenant(record.id.value, uuid4()) is None


def test_listing_filters_orders_newest_first_and_pages(conn):
    repo, source = PostgresIntakeRecordRepository(conn), seed_source(conn)
    job = seed_job(conn, source)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    records = [repo.save(_record(source, received_at=base + timedelta(minutes=i), job_id=job.id.value))
               for i in range(3)]
    repo.save(_record(source))  # no job
    repo.save(_rejected(source))
    tenant_id = source.tenant_id.value

    in_job = repo.list_by_tenant(tenant_id, status=IntakeRecordStatus.PENDING, job_id=job.id.value)

    assert [r.id.value for r in in_job] == [r.id.value for r in reversed(records)]
    assert [r.id.value for r in repo.list_by_tenant(tenant_id, job_id=job.id.value, limit=1, offset=1)] == [
        records[1].id.value]
    assert repo.count_by_tenant(tenant_id) == 5
    assert repo.count_by_tenant(tenant_id, status=IntakeRecordStatus.REJECTED) == 1
    assert repo.count_by_tenant(tenant_id, status=IntakeRecordStatus.PENDING, job_id=job.id.value) == 3
    assert repo.count_by_tenant(uuid4()) == 0


def test_count_by_source_counts_the_records_of_that_source_in_that_organization(conn):
    repo, source = PostgresIntakeRecordRepository(conn), seed_source(conn)
    repo.save(_record(source))
    repo.save(_record(source))
    repo.save(_record(seed_source(conn)))

    assert repo.count_by_source(source.tenant_id.value, source.id.value) == 2
    assert repo.count_by_source(uuid4(), source.id.value) == 0


@pytest.mark.parametrize("status", list(IntakeRecordStatus))
def test_only_a_pending_or_rejected_record_can_be_claimed(conn, status):
    repo, source = PostgresIntakeRecordRepository(conn), seed_source(conn)
    record = repo.save(_record(source, status=status))

    claimed = repo.claim_unpromoted(record.id.value, source.tenant_id.value)

    assert (claimed is not None) == (status in _OPEN)


def test_claiming_a_record_of_another_organization_or_a_missing_one_returns_none(conn):
    repo, source = PostgresIntakeRecordRepository(conn), seed_source(conn)
    record = repo.save(_record(source))

    assert repo.claim_unpromoted(record.id.value, uuid4()) is None
    assert repo.claim_unpromoted(uuid4(), source.tenant_id.value) is None


def test_the_lead_id_is_an_external_uuid_that_needs_no_lead_row(conn):
    repo, source = PostgresIntakeRecordRepository(conn), seed_source(conn)
    record = _record(source)
    lead_id = uuid4()
    record.promote(lead_id)
    repo.save(record)

    found = repo.get_by_id_and_tenant(record.id.value, source.tenant_id.value)

    assert (found.status, found.lead_id.value) == (IntakeRecordStatus.PROMOTED, lead_id)


def test_a_record_with_a_blank_budget_cell_still_persists_what_arrived(conn):
    """ADR-0009: what arrives is stored before anything tries to interpret it. A NaN
    budget used to fail this insert and take every other row of the batch with it."""
    repo, source = PostgresIntakeRecordRepository(conn), seed_source(conn)
    record = repo.save(_record(source, payload={
        "first_name": "Juan", "budget": float("nan"), "custom_attributes": {"nested": [float("inf")]},
    }))

    found = repo.get_by_id_and_tenant(record.id.value, source.tenant_id.value)

    assert found.payload == {"first_name": "Juan", "budget": None, "custom_attributes": {"nested": [None]}}
