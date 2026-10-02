import uuid
from datetime import datetime, timezone
from uuid import UUID

from chassis.outbox import OutboxRow
from chassis.web import request_id_var

from application.dtos.commands import IngestLeadCommand, ReceiveIntakeCommand
from application.use_cases.ingest_lead_use_case import IngestLeadUseCase
from application.use_cases.receive_intake_use_case import ReceiveIntakeUseCase
from domain.entities.lead_source import LeadSource
from domain.services.assignment_engine import AssignmentEngine
from domain.value_objects.enums import IntakeJobKind, IntakeJobStatus, IntakeRecordStatus, LeadSourceKind
from infrastructure.intake_worker import messages as job_messages
from infrastructure.adapters.output.queue.job_message import job_message
from infrastructure.intake_worker.messages import process_job_message
from tests.unit.mocks.in_memory_uow import InMemoryUnitOfWork

_PAYLOAD = {
    "first_name": "Maria", "last_name": "Gomez", "company": "TechCorp",
    "budget": 5000, "industry": "Tech", "email": "mgomez@techcorp.com",
}


class _Parser:
    def parse_leads_file(self, file_content, filename, tenant_id, source_id):
        return [IngestLeadCommand(tenant_id=tenant_id, source_id=source_id, **_PAYLOAD)]


class _Container:
    """Just what the job wiring reads: one shared in-memory unit of work."""

    def __init__(self, uow: InMemoryUnitOfWork) -> None:
        self._uow = uow
        self.assignment_engine = AssignmentEngine()
        self.file_parser = _Parser()

    def unit_of_work(self) -> InMemoryUnitOfWork:
        return self._uow


class _FailingIngest:
    def execute(self, command, existing_record=None):
        raise RuntimeError("scoring blew up")


class _SpyIngest:
    def __init__(self, real) -> None:
        self.real, self.request_ids = real, []

    def execute(self, command, existing_record=None):
        self.request_ids.append(request_id_var.get())
        return self.real.execute(command, existing_record=existing_record)


def _received(kind: IntakeJobKind):
    tenant_id = uuid.uuid4()
    uow = InMemoryUnitOfWork()
    uow.sources.save(LeadSource.create(tenant_id=tenant_id, name="Form", kind=LeadSourceKind.MANUAL_FORM))
    uow.sources.save(LeadSource.create(tenant_id=tenant_id, name="Upload", kind=LeadSourceKind.FILE_UPLOAD))
    batch = kind == IntakeJobKind.BATCH
    received = ReceiveIntakeUseCase(uow=uow).execute(ReceiveIntakeCommand(
        tenant_id=tenant_id, kind=kind.value, payloads=[] if batch else [_PAYLOAD],
        filename="leads.csv" if batch else None, content=b"irrelevant" if batch else None,
    ))
    message = {"tenant_id": str(tenant_id), "job_id": received.job_id, "correlation_id": "req-42"}
    return uow, tenant_id, UUID(received.job_id), message


def test_a_record_that_raises_nacks_and_leaves_the_job_unfinished(monkeypatch):
    uow, tenant_id, job_id, message = _received(IntakeJobKind.SINGLE)
    monkeypatch.setattr(job_messages, "get_ingest_lead_use_case", lambda uow, container: _FailingIngest())

    assert process_job_message(_Container(uow), message) == "nack"

    [record] = uow.intake_records.list_by_tenant(tenant_id, job_id=job_id)
    assert record.status == IntakeRecordStatus.PENDING
    assert uow.intake_jobs.get_by_id_and_tenant(job_id, tenant_id).status != IntakeJobStatus.COMPLETED


def test_a_job_that_runs_through_acks_and_completes():
    uow, tenant_id, job_id, message = _received(IntakeJobKind.SINGLE)

    assert process_job_message(_Container(uow), message) == "ack"

    assert uow.intake_jobs.get_by_id_and_tenant(job_id, tenant_id).status == IntakeJobStatus.COMPLETED


def test_a_batch_job_parses_its_stored_file_before_processing():
    uow, tenant_id, job_id, message = _received(IntakeJobKind.BATCH)

    assert process_job_message(_Container(uow), message) == "ack"

    [record] = uow.intake_records.list_by_tenant(tenant_id, job_id=job_id)
    assert record.status == IntakeRecordStatus.PROMOTED
    job = uow.intake_jobs.get_by_id_and_tenant(job_id, tenant_id)
    assert (job.status, job.total_items, job.succeeded) == (IntakeJobStatus.COMPLETED, 1, 1)


def test_a_job_that_does_not_exist_is_acked():
    message = {"tenant_id": str(uuid.uuid4()), "job_id": str(uuid.uuid4()), "correlation_id": None}

    assert process_job_message(_Container(InMemoryUnitOfWork()), message) == "ack"


def test_a_redelivered_message_for_a_finished_job_is_acked():
    uow, _, _, message = _received(IntakeJobKind.SINGLE)
    process_job_message(_Container(uow), message)

    assert process_job_message(_Container(uow), message) == "ack"


def test_the_work_runs_under_the_correlation_id_of_the_request(monkeypatch):
    uow, _, _, message = _received(IntakeJobKind.SINGLE)
    spy = _SpyIngest(IngestLeadUseCase(uow=uow))
    monkeypatch.setattr(job_messages, "get_ingest_lead_use_case", lambda uow, container: spy)

    process_job_message(_Container(uow), message)

    assert spy.request_ids == ["req-42"]
    assert request_id_var.get() == "-"


def test_the_job_message_carries_its_outbox_id_and_correlation_id():
    row = OutboxRow(
        id=uuid.uuid4(), channel="job", tenant_id="t-1", partition_key="j-1",
        event_type="IntakeJobRequested", payload={"tenant_id": "t-1", "job_id": "j-1"},
        occurred_on=datetime.now(timezone.utc), correlation_id="req-42",
    )

    assert job_message(row) == {
        "message_id": str(row.id), "schema_version": 1,
        "tenant_id": "t-1", "job_id": "j-1", "correlation_id": "req-42",
    }
