"""Reception stores the work and queues it; parsing a batch only materialises its records."""
from typing import Optional
from uuid import UUID, uuid4

import pytest

from application.dtos.reception import IngestLeadCommand, ReceiveIntakeCommand
from application.use_cases.reception.process_batch import ProcessBatchUseCase
from application.use_cases.reception.receive_intake import ReceiveIntakeUseCase
from domain.exceptions import DomainException
from domain.sources.lead_source import LeadSource
from domain.value_objects.enums import IntakeJobKind, IntakeJobStatus, IntakeRecordStatus, LeadSourceKind
from tests.unit.application.doubles.uow import InMemoryUnitOfWork

_PAYLOAD = {"first_name": "Maria", "last_name": "Gomez", "company": "TechCorp", "budget": 5000,
            "industry": "Tech", "email": "mgomez@techcorp.com"}


def _seeded(tenant_id: UUID) -> InMemoryUnitOfWork:
    uow = InMemoryUnitOfWork()
    uow.sources.save(LeadSource.create(tenant_id=tenant_id, name="Form", kind=LeadSourceKind.MANUAL_FORM))
    uow.sources.save(LeadSource.create(tenant_id=tenant_id, name="Upload", kind=LeadSourceKind.FILE_UPLOAD))
    return uow


def _single(uow, tenant_id):
    return ReceiveIntakeUseCase(uow).execute(
        ReceiveIntakeCommand(tenant_id=tenant_id, kind=IntakeJobKind.SINGLE.value, payloads=[_PAYLOAD]))


def _batch(uow, tenant_id) -> UUID:
    received = ReceiveIntakeUseCase(uow).execute(ReceiveIntakeCommand(
        tenant_id=tenant_id, kind=IntakeJobKind.BATCH.value, payloads=[],
        filename="leads.csv", content=b"first_name\nMaria\n"))
    return UUID(received.job_id)


class _StubParser:
    def __init__(self, rows=None, error: Optional[Exception] = None) -> None:
        self.rows, self.error, self.calls = rows or [], error, 0

    def parse_leads_file(self, file_content, filename, tenant_id, source_id):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return [IngestLeadCommand(tenant_id=tenant_id, source_id=source_id, **row) for row in self.rows]


def test_a_single_lead_creates_a_pending_job_with_one_pending_record_and_queues_the_job():
    tenant_id = uuid4()
    uow = _seeded(tenant_id)

    result = _single(uow, tenant_id)

    job = uow.intake_jobs.get_by_id_and_tenant(UUID(result.job_id), tenant_id)
    assert (job.status, job.total_items, len(result.record_ids)) == (IntakeJobStatus.PENDING, 1, 1)
    record = uow.intake_records.get_by_id_and_tenant(UUID(result.record_ids[0]), tenant_id)
    assert record.status == IntakeRecordStatus.PENDING and str(record.job_id) == result.job_id
    [event] = uow.events("IntakeJobRequested")
    assert (event.channel, event.partition_key) == ("job", result.job_id)
    assert event.payload == {"tenant_id": str(tenant_id), "job_id": result.job_id}


def test_a_batch_stores_its_file_and_has_no_total_until_parsed():
    tenant_id = uuid4()
    uow = _seeded(tenant_id)

    job_id = _batch(uow, tenant_id)

    stored = uow.intake_files.get(job_id, tenant_id)
    assert (stored.filename, stored.content, stored.parsed_at) == ("leads.csv", b"first_name\nMaria\n", None)
    assert uow.intake_jobs.get_by_id_and_tenant(job_id, tenant_id).total_items is None
    assert [e.payload["job_id"] for e in uow.events("IntakeJobRequested")] == [str(job_id)]


def test_receiving_without_the_organizations_source_fails():
    tenant_id = uuid4()

    with pytest.raises(DomainException) as caught:
        _single(InMemoryUnitOfWork(), tenant_id)

    assert caught.value.error_code == "SOURCE_NOT_FOUND"


def test_a_reception_that_rolls_back_leaves_no_job_in_the_outbox():
    class _FailingRecords:
        def save(self, record):
            raise RuntimeError("database gone")

    tenant_id = uuid4()
    uow = _seeded(tenant_id)
    uow.intake_records = _FailingRecords()

    with pytest.raises(RuntimeError):
        _single(uow, tenant_id)

    assert uow.events() == []


def test_parsing_creates_one_record_per_row_and_a_redelivery_does_not_repeat_it():
    tenant_id = uuid4()
    uow = _seeded(tenant_id)
    job_id = _batch(uow, tenant_id)
    parser = _StubParser(rows=[dict(_PAYLOAD, budget=5000.0)])
    parse = ProcessBatchUseCase(uow, parser)

    parse.execute(tenant_id, job_id)
    parse.execute(tenant_id, job_id)

    assert parser.calls == 1
    assert uow.intake_records.count_by_tenant(tenant_id, job_id=job_id) == 1
    job = uow.intake_jobs.get_by_id_and_tenant(job_id, tenant_id)
    assert (job.status, job.total_items) == (IntakeJobStatus.PENDING, 1)
    assert uow.intake_files.get(job_id, tenant_id).parsed_at is not None


def test_an_unreadable_file_fails_the_job_without_records():
    tenant_id = uuid4()
    uow = _seeded(tenant_id)
    job_id = _batch(uow, tenant_id)

    ProcessBatchUseCase(uow, _StubParser(error=ValueError("not a csv"))).execute(tenant_id, job_id)

    assert uow.intake_jobs.get_by_id_and_tenant(job_id, tenant_id).status == IntakeJobStatus.FAILED
    assert uow.intake_records.count_by_tenant(tenant_id, job_id=job_id) == 0


def test_parsing_a_job_of_another_organization_is_not_found():
    tenant_id = uuid4()
    uow = _seeded(tenant_id)
    job_id = _batch(uow, tenant_id)

    with pytest.raises(DomainException) as caught:
        ProcessBatchUseCase(uow, _StubParser()).execute(uuid4(), job_id)

    assert caught.value.error_code == "INTAKE_JOB_NOT_FOUND"
