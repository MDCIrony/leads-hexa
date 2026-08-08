from typing import Optional
from uuid import UUID, uuid4

import pytest

from application.dtos.commands import IngestLeadCommand, LeadProcessedResult, ReceiveIntakeCommand
from application.ports.input.ingest_lead_use_case_port import IngestLeadInputPort
from application.use_cases.ingest_lead_use_case import IngestLeadUseCase
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
    assert job.failed == 1
    assert job.succeeded == 1  # the other item was unaffected

    exploded = uow.intake_records.get_by_id_and_tenant(exploding_record_id, tenant_id)
    assert exploded is not None
    assert exploded.status == IntakeRecordStatus.PENDING
    assert exploded.payload == exploding_payload

    other = uow.intake_records.get_by_id_and_tenant(other_record_id, tenant_id)
    assert other.status == IntakeRecordStatus.PROMOTED
