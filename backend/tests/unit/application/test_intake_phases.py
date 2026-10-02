from typing import Optional
from uuid import UUID, uuid4

import pytest

from application.dtos.commands import IngestLeadCommand, LeadProcessedResult, ReceiveIntakeCommand
from application.ports.input.ingest_lead_use_case_port import IngestLeadInputPort
from application.use_cases.ingest_lead_use_case import IngestLeadUseCase
from application.use_cases.intake_job_use_cases import ReprocessIntakeJobUseCase
from application.use_cases.process_batch_use_case import ProcessBatchUseCase
from application.use_cases.process_intake_job_use_case import ProcessIntakeJobUseCase
from application.use_cases.receive_intake_use_case import ReceiveIntakeUseCase
from domain.entities.intake_record import IntakeRecord
from domain.entities.lead_source import LeadSource
from domain.exceptions import DomainException
from domain.value_objects.enums import IntakeJobKind, IntakeJobStatus, IntakeRecordStatus, LeadSourceKind
from tests.unit.mocks.in_memory_uow import InMemoryUnitOfWork

_VALID_PAYLOAD = {
    "first_name": "Maria",
    "last_name": "Gomez",
    "company": "TechCorp",
    "budget": 5000,
    "industry": "Tech",
    "email": "mgomez@techcorp.com",
}

_INVALID_PAYLOAD = {
    "first_name": "Bad",
    "last_name": "Lead",
    "company": "Corp",
    "budget": 1000,
    "industry": "Tech",
    "email": "not-an-email",
}


def _seeded_uow(tenant_id: UUID) -> InMemoryUnitOfWork:
    # ReceiveIntakeUseCase resolves the source by kind: an empty UoW would
    # fail every test in this module with SOURCE_NOT_FOUND.
    uow = InMemoryUnitOfWork()
    uow.sources.save(LeadSource.create(tenant_id=tenant_id, name="Form", kind=LeadSourceKind.MANUAL_FORM))
    uow.sources.save(LeadSource.create(tenant_id=tenant_id, name="Upload", kind=LeadSourceKind.FILE_UPLOAD))
    return uow


class _ExplodingIngest(IngestLeadInputPort):
    """Delegates to a real IngestLeadUseCase for every payload except one,
    where it raises instead. The double the task calls for: it proves a crash
    on one item does not stop the run or lose the record that caused it."""

    def __init__(self, real: IngestLeadInputPort, explode_on_email: str) -> None:
        self._real = real
        self._explode_on_email = explode_on_email

    def resolve_source_id(self, tenant_id, kind):
        return self._real.resolve_source_id(tenant_id, kind)

    def execute(
        self, command: IngestLeadCommand, existing_record: Optional[IntakeRecord] = None
    ) -> LeadProcessedResult:
        if command.email == self._explode_on_email:
            raise RuntimeError("boom")
        return self._real.execute(command, existing_record=existing_record)


# --- ReceiveIntakeUseCase ---


def test_receiving_a_single_lead_creates_a_job_and_one_pending_record():
    tenant_id = uuid4()
    uow = _seeded_uow(tenant_id)
    use_case = ReceiveIntakeUseCase(uow=uow)

    result = use_case.execute(
        ReceiveIntakeCommand(tenant_id=tenant_id, kind=IntakeJobKind.SINGLE.value, payloads=[_VALID_PAYLOAD])
    )

    job = uow.intake_jobs.get_by_id_and_tenant(UUID(result.job_id), tenant_id)
    assert job is not None
    assert job.status == IntakeJobStatus.PENDING
    assert job.total_items == 1
    assert len(result.record_ids) == 1
    record = uow.intake_records.get_by_id_and_tenant(UUID(result.record_ids[0]), tenant_id)
    assert record is not None
    assert record.status == IntakeRecordStatus.PENDING
    assert record.job_id is not None
    assert str(record.job_id) == result.job_id


def test_receiving_a_batch_with_no_payloads_yet_has_no_total():
    tenant_id = uuid4()
    uow = _seeded_uow(tenant_id)
    use_case = ReceiveIntakeUseCase(uow=uow)

    result = use_case.execute(
        ReceiveIntakeCommand(tenant_id=tenant_id, kind=IntakeJobKind.BATCH.value, payloads=[])
    )

    job = uow.intake_jobs.get_by_id_and_tenant(UUID(result.job_id), tenant_id)
    assert job is not None
    assert job.status == IntakeJobStatus.PENDING
    assert job.total_items is None
    assert result.record_ids == []


def test_receiving_without_an_active_source_fails():
    tenant_id = uuid4()
    uow = InMemoryUnitOfWork()  # deliberately unseeded

    with pytest.raises(DomainException) as exc_info:
        ReceiveIntakeUseCase(uow=uow).execute(
            ReceiveIntakeCommand(tenant_id=tenant_id, kind=IntakeJobKind.SINGLE.value, payloads=[_VALID_PAYLOAD])
        )

    assert exc_info.value.error_code == "SOURCE_NOT_FOUND"


# --- ProcessIntakeJobUseCase ---


def test_processing_a_job_with_a_valid_payload_completes_and_promotes():
    tenant_id = uuid4()
    uow = _seeded_uow(tenant_id)
    received = ReceiveIntakeUseCase(uow=uow).execute(
        ReceiveIntakeCommand(tenant_id=tenant_id, kind=IntakeJobKind.SINGLE.value, payloads=[_VALID_PAYLOAD])
    )

    ProcessIntakeJobUseCase(uow=uow, ingest=IngestLeadUseCase(uow=uow)).execute(
        tenant_id=tenant_id, job_id=UUID(received.job_id)
    )

    job = uow.intake_jobs.get_by_id_and_tenant(UUID(received.job_id), tenant_id)
    assert job.status == IntakeJobStatus.COMPLETED
    assert job.succeeded == 1
    assert job.failed == 0
    record = uow.intake_records.get_by_id_and_tenant(UUID(received.record_ids[0]), tenant_id)
    assert record.status == IntakeRecordStatus.PROMOTED
    assert record.lead_id is not None
    assert uow.leads.get_by_id_and_tenant(record.lead_id.value, tenant_id) is not None


def test_processing_a_job_with_an_invalid_payload_completes_and_rejects():
    tenant_id = uuid4()
    uow = _seeded_uow(tenant_id)
    received = ReceiveIntakeUseCase(uow=uow).execute(
        ReceiveIntakeCommand(tenant_id=tenant_id, kind=IntakeJobKind.SINGLE.value, payloads=[_INVALID_PAYLOAD])
    )

    ProcessIntakeJobUseCase(uow=uow, ingest=IngestLeadUseCase(uow=uow)).execute(
        tenant_id=tenant_id, job_id=UUID(received.job_id)
    )

    job = uow.intake_jobs.get_by_id_and_tenant(UUID(received.job_id), tenant_id)
    assert job.status == IntakeJobStatus.COMPLETED
    assert job.succeeded == 0
    assert job.failed == 1
    record = uow.intake_records.get_by_id_and_tenant(UUID(received.record_ids[0]), tenant_id)
    assert record.status == IntakeRecordStatus.REJECTED
    assert record.errors[0].field == "email"


def test_processing_a_mixed_job_counts_both_and_leaves_both_terminal():
    tenant_id = uuid4()
    uow = _seeded_uow(tenant_id)
    received = ReceiveIntakeUseCase(uow=uow).execute(
        ReceiveIntakeCommand(
            tenant_id=tenant_id, kind=IntakeJobKind.BATCH.value, payloads=[_VALID_PAYLOAD, _INVALID_PAYLOAD]
        )
    )

    ProcessIntakeJobUseCase(uow=uow, ingest=IngestLeadUseCase(uow=uow)).execute(
        tenant_id=tenant_id, job_id=UUID(received.job_id)
    )

    job = uow.intake_jobs.get_by_id_and_tenant(UUID(received.job_id), tenant_id)
    assert job.succeeded == 1
    assert job.failed == 1
    statuses = {
        uow.intake_records.get_by_id_and_tenant(UUID(rid), tenant_id).status for rid in received.record_ids
    }
    assert statuses == {IntakeRecordStatus.PROMOTED, IntakeRecordStatus.REJECTED}


def test_processing_a_job_from_another_organization_is_not_found():
    tenant_id = uuid4()
    other_tenant_id = uuid4()
    uow = _seeded_uow(tenant_id)
    received = ReceiveIntakeUseCase(uow=uow).execute(
        ReceiveIntakeCommand(tenant_id=tenant_id, kind=IntakeJobKind.SINGLE.value, payloads=[_VALID_PAYLOAD])
    )

    with pytest.raises(DomainException) as exc_info:
        ProcessIntakeJobUseCase(uow=uow, ingest=IngestLeadUseCase(uow=uow)).execute(
            tenant_id=other_tenant_id, job_id=UUID(received.job_id)
        )

    assert exc_info.value.error_code == "INTAKE_JOB_NOT_FOUND"


def test_listing_records_by_job_id_returns_only_that_jobs_records():
    tenant_id = uuid4()
    uow = _seeded_uow(tenant_id)
    receive = ReceiveIntakeUseCase(uow=uow)
    first = receive.execute(
        ReceiveIntakeCommand(tenant_id=tenant_id, kind=IntakeJobKind.SINGLE.value, payloads=[_VALID_PAYLOAD])
    )
    receive.execute(
        ReceiveIntakeCommand(tenant_id=tenant_id, kind=IntakeJobKind.SINGLE.value, payloads=[_VALID_PAYLOAD])
    )

    found = uow.intake_records.list_by_tenant(tenant_id, job_id=UUID(first.job_id))

    assert [str(r.id) for r in found] == first.record_ids


# --- the test that justifies the whole phase split ---


def test_an_unforeseen_failure_does_not_lose_the_record_and_the_run_continues():
    tenant_id = uuid4()
    uow = _seeded_uow(tenant_id)
    exploding_payload = dict(_VALID_PAYLOAD, email="explodes@example.com")
    other_payload = dict(_VALID_PAYLOAD, email="fine@example.com")

    received = ReceiveIntakeUseCase(uow=uow).execute(
        ReceiveIntakeCommand(
            tenant_id=tenant_id, kind=IntakeJobKind.BATCH.value, payloads=[exploding_payload, other_payload]
        )
    )
    exploding_record_id, other_record_id = (UUID(r) for r in received.record_ids)

    ingest = _ExplodingIngest(IngestLeadUseCase(uow=uow), explode_on_email="explodes@example.com")
    ProcessIntakeJobUseCase(uow=uow, ingest=ingest).execute(tenant_id=tenant_id, job_id=UUID(received.job_id))

    job = uow.intake_jobs.get_by_id_and_tenant(UUID(received.job_id), tenant_id)
    # Interrupted, not COMPLETED: a completed job would refuse the reprocess
    # that is supposed to pick this record back up.
    assert job.status == IntakeJobStatus.PROCESSING
    # Not counted as failed: the record is still PENDING, waiting for the
    # reprocess that will pick it up. Counters are derived from the records,
    # so they say "not done yet" rather than "failed" — which is the truth.
    assert job.failed == 0
    assert job.succeeded == 1  # the other item was unaffected

    exploded = uow.intake_records.get_by_id_and_tenant(exploding_record_id, tenant_id)
    assert exploded is not None
    assert exploded.status == IntakeRecordStatus.PENDING
    assert exploded.payload == exploding_payload

    other = uow.intake_records.get_by_id_and_tenant(other_record_id, tenant_id)
    assert other.status == IntakeRecordStatus.PROMOTED


def test_a_run_that_dies_before_saving_recovers_its_counters():
    """The counters used to live in memory for the whole loop and only reach
    the database at the end: a process that died at item 9,000 lost all
    9,000 and the job came back saying 0/0. Derived from the records, the
    next pass reads the truth off what actually got promoted."""
    tenant_id = uuid4()
    uow = _seeded_uow(tenant_id)
    received = ReceiveIntakeUseCase(uow=uow).execute(
        ReceiveIntakeCommand(
            tenant_id=tenant_id,
            kind=IntakeJobKind.BATCH.value,
            payloads=[_VALID_PAYLOAD, dict(_VALID_PAYLOAD, email="second@techcorp.com")],
        )
    )
    job_id = UUID(received.job_id)
    process = ProcessIntakeJobUseCase(uow=uow, ingest=IngestLeadUseCase(uow=uow))
    process.execute(tenant_id=tenant_id, job_id=job_id)

    # The records were promoted one transaction at a time and survived; the
    # counters are what a dead process would have taken with it.
    job = uow.intake_jobs.get_by_id_and_tenant(job_id, tenant_id)
    job.status, job.succeeded, job.failed, job.completed_at = IntakeJobStatus.PROCESSING, 0, 0, None
    uow.intake_jobs.save(job)

    process.execute(tenant_id=tenant_id, job_id=job_id)

    recovered = uow.intake_jobs.get_by_id_and_tenant(job_id, tenant_id)
    assert (recovered.succeeded, recovered.failed) == (2, 0)


def test_reprocessing_a_job_left_in_progress_does_not_duplicate_leads():
    """What at-least-once delivery will look like: the same job processed
    twice. Only PENDING records are read, so the lead promoted on the first
    pass is not created again on the second."""
    tenant_id = uuid4()
    uow = _seeded_uow(tenant_id)
    received = ReceiveIntakeUseCase(uow=uow).execute(
        ReceiveIntakeCommand(tenant_id=tenant_id, kind=IntakeJobKind.SINGLE.value, payloads=[_VALID_PAYLOAD])
    )
    process = ProcessIntakeJobUseCase(uow=uow, ingest=IngestLeadUseCase(uow=uow))
    process.execute(tenant_id=tenant_id, job_id=UUID(received.job_id))

    # The state a worker that died mid-run leaves behind, which is what a
    # redelivered message finds.
    job = uow.intake_jobs.get_by_id_and_tenant(UUID(received.job_id), tenant_id)
    job.status = IntakeJobStatus.PROCESSING
    uow.intake_jobs.save(job)

    process.execute(tenant_id=tenant_id, job_id=UUID(received.job_id))

    assert len(uow.leads.list_by_tenant(tenant_id)) == 1


# --- background work goes through the outbox (F1) ---


def _job_rows(uow: InMemoryUnitOfWork):
    return uow.outbox.list_unpublished("job", 100)


class _FailingRecords:
    def save(self, record):
        raise RuntimeError("database gone")


class _StubParser:
    def __init__(self, rows=None, error: Optional[Exception] = None) -> None:
        self.rows, self.error, self.calls = rows or [], error, 0

    def parse_leads_file(self, file_content, filename, tenant_id, source_id):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return [
            IngestLeadCommand(tenant_id=tenant_id, source_id=source_id, **row) for row in self.rows
        ]


def _receive_batch(uow: InMemoryUnitOfWork, tenant_id: UUID) -> UUID:
    received = ReceiveIntakeUseCase(uow=uow).execute(ReceiveIntakeCommand(
        tenant_id=tenant_id, kind=IntakeJobKind.BATCH.value, payloads=[],
        filename="leads.csv", content=b"first_name\nMaria\n",
    ))
    return UUID(received.job_id)


def test_receiving_a_single_lead_records_its_job_in_the_outbox():
    tenant_id = uuid4()
    uow = _seeded_uow(tenant_id)

    received = ReceiveIntakeUseCase(uow=uow).execute(
        ReceiveIntakeCommand(tenant_id=tenant_id, kind=IntakeJobKind.SINGLE.value, payloads=[_VALID_PAYLOAD])
    )

    [row] = _job_rows(uow)
    assert row.payload == {"tenant_id": str(tenant_id), "job_id": received.job_id}
    assert row.partition_key == received.job_id
    assert row.event_type == "IntakeJobRequested"


def test_a_reception_that_rolls_back_leaves_no_job_in_the_outbox():
    tenant_id = uuid4()
    uow = _seeded_uow(tenant_id)
    uow.intake_records = _FailingRecords()

    with pytest.raises(RuntimeError):
        ReceiveIntakeUseCase(uow=uow).execute(
            ReceiveIntakeCommand(tenant_id=tenant_id, kind=IntakeJobKind.SINGLE.value, payloads=[_VALID_PAYLOAD])
        )

    assert _job_rows(uow) == []


def test_receiving_a_batch_stores_the_file_and_records_its_job():
    tenant_id = uuid4()
    uow = _seeded_uow(tenant_id)

    job_id = _receive_batch(uow, tenant_id)

    stored = uow.intake_files.get(job_id, tenant_id)
    assert (stored.filename, stored.content, stored.parsed_at) == ("leads.csv", b"first_name\nMaria\n", None)
    assert [row.payload["job_id"] for row in _job_rows(uow)] == [str(job_id)]


def test_parsing_the_stored_file_twice_does_not_duplicate_records():
    """A redelivered job message parses again; parsed_at is what stops it."""
    tenant_id = uuid4()
    uow = _seeded_uow(tenant_id)
    job_id = _receive_batch(uow, tenant_id)
    parser = _StubParser(rows=[{
        "first_name": "Maria", "last_name": "Gomez", "company": "TechCorp",
        "budget": 5000.0, "industry": "Tech", "email": "mgomez@techcorp.com",
    }])
    parse = ProcessBatchUseCase(uow=uow, file_parser=parser)

    parse.execute(tenant_id, job_id)
    parse.execute(tenant_id, job_id)

    assert parser.calls == 1
    assert uow.intake_records.count_by_tenant(tenant_id, job_id=job_id) == 1
    job = uow.intake_jobs.get_by_id_and_tenant(job_id, tenant_id)
    assert (job.status, job.total_items) == (IntakeJobStatus.PENDING, 1)
    assert uow.intake_files.get(job_id, tenant_id).parsed_at is not None


def test_an_unreadable_stored_file_fails_the_job_without_records():
    tenant_id = uuid4()
    uow = _seeded_uow(tenant_id)
    job_id = _receive_batch(uow, tenant_id)

    ProcessBatchUseCase(uow=uow, file_parser=_StubParser(error=ValueError("not a csv"))).execute(tenant_id, job_id)

    assert uow.intake_jobs.get_by_id_and_tenant(job_id, tenant_id).status == IntakeJobStatus.FAILED
    assert uow.intake_records.count_by_tenant(tenant_id, job_id=job_id) == 0


def test_processing_reports_whether_the_run_was_interrupted():
    tenant_id = uuid4()
    uow = _seeded_uow(tenant_id)
    received = ReceiveIntakeUseCase(uow=uow).execute(
        ReceiveIntakeCommand(tenant_id=tenant_id, kind=IntakeJobKind.SINGLE.value, payloads=[_VALID_PAYLOAD])
    )
    exploding = _ExplodingIngest(IngestLeadUseCase(uow=uow), explode_on_email=_VALID_PAYLOAD["email"])

    assert ProcessIntakeJobUseCase(uow=uow, ingest=exploding).execute(tenant_id, UUID(received.job_id)) is True
    assert ProcessIntakeJobUseCase(uow=uow, ingest=IngestLeadUseCase(uow=uow)).execute(
        tenant_id, UUID(received.job_id)
    ) is False


def test_reprocessing_records_a_job_and_does_not_process_in_line():
    tenant_id = uuid4()
    uow = _seeded_uow(tenant_id)
    received = ReceiveIntakeUseCase(uow=uow).execute(
        ReceiveIntakeCommand(tenant_id=tenant_id, kind=IntakeJobKind.SINGLE.value, payloads=[_VALID_PAYLOAD])
    )
    job_id = UUID(received.job_id)
    uow.outbox.mark_published(_job_rows(uow)[0].id)

    ReprocessIntakeJobUseCase(uow=uow).execute(tenant_id, job_id)

    assert [row.payload["job_id"] for row in _job_rows(uow)] == [str(job_id)]
    assert uow.intake_jobs.get_by_id_and_tenant(job_id, tenant_id).status == IntakeJobStatus.PENDING
    record = uow.intake_records.get_by_id_and_tenant(UUID(received.record_ids[0]), tenant_id)
    assert record.status == IntakeRecordStatus.PENDING
