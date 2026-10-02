import uuid
from typing import List

from application.dtos.commands import IngestLeadCommand
from application.use_cases.process_batch_use_case import ProcessBatchUseCase
from application.use_cases.process_intake_job_use_case import ProcessIntakeJobUseCase
from domain.entities.intake_job import IntakeJob
from domain.entities.intake_record import IntakeRecord
from domain.value_objects.enums import IntakeJobKind, IntakeJobStatus, IntakeRecordStatus
from tests.unit.mocks.in_memory_lead_repo import InMemoryLeadRepository
from tests.unit.mocks.in_memory_rule_repo import InMemoryRuleRepository
from tests.unit.mocks.in_memory_sales_group_repo import InMemorySalesGroupRepository
from tests.unit.mocks.in_memory_uow import InMemoryUnitOfWork
from tests.unit.mocks.in_process_ingest import in_process_ingest


def _command(**overrides) -> IngestLeadCommand:
    defaults = dict(
        tenant_id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        first_name="Jane",
        last_name="Doe",
        company="Acme Corp",
        budget=5000.0,
        industry="Tech",
        email="jane@example.com",
    )
    defaults.update(overrides)
    return IngestLeadCommand(**defaults)


def _new_uow() -> InMemoryUnitOfWork:
    return InMemoryUnitOfWork(
        InMemoryLeadRepository(),
        InMemoryRuleRepository(),
        groups=InMemorySalesGroupRepository(),
    )


class _StubFileParser:
    """Hands back pre-built commands instead of parsing bytes: what matters
    here is what ProcessBatchUseCase does with each row's result, not CSV
    parsing itself."""

    def __init__(self, commands: List[IngestLeadCommand]) -> None:
        self._commands = commands

    def parse_leads_file(self, file_content, filename, tenant_id, source_id) -> List[IngestLeadCommand]:
        return self._commands


def _existing_record(uow: InMemoryUnitOfWork, command: IngestLeadCommand) -> IntakeRecord:
    # F2d: IngestLeadUseCase no longer creates its own row — the caller
    # always persists it first, the way ReceiveIntakeUseCase does.
    return uow.intake_records.save(IntakeRecord.create(
        tenant_id=command.tenant_id, source_id=command.source_id, payload={},
    ))


def test_valid_payload_promotes_the_intake_record_to_the_created_lead():
    tenant_id = uuid.uuid4()
    uow = _new_uow()
    use_case = in_process_ingest(uow)
    command = _command(tenant_id=tenant_id)
    existing = _existing_record(uow, command)

    result = use_case.execute(command, existing_record=existing)

    assert result.error is None
    assert result.lead_id != ""
    record = uow.intake_records.get_by_id_and_tenant(uuid.UUID(result.intake_record_id), tenant_id)
    assert record is not None
    assert record.status == IntakeRecordStatus.PROMOTED
    assert str(record.lead_id) == result.lead_id


def test_invalid_email_rejects_the_intake_record_without_creating_a_lead():
    tenant_id = uuid.uuid4()
    uow = _new_uow()
    use_case = in_process_ingest(uow)
    command = _command(tenant_id=tenant_id, email="not-an-email")
    existing = _existing_record(uow, command)

    result = use_case.execute(command, existing_record=existing)

    assert result.lead_id == ""
    assert result.intake_record_id != ""
    record = uow.intake_records.get_by_id_and_tenant(uuid.UUID(result.intake_record_id), tenant_id)
    assert record is not None
    assert record.status == IntakeRecordStatus.REJECTED
    assert record.lead_id is None
    assert len(record.errors) == 1
    assert record.errors[0].field == "email"


def test_payload_without_email_still_promotes_the_lead():
    # T2 (optional email) and T4 (unified pipeline) must not step on each
    # other: a missing email is valid data, not a rejection.
    tenant_id = uuid.uuid4()
    uow = _new_uow()
    use_case = in_process_ingest(uow)
    command = _command(tenant_id=tenant_id, email=None)
    existing = _existing_record(uow, command)

    result = use_case.execute(command, existing_record=existing)

    assert result.error is None
    assert result.lead_id != ""
    record = uow.intake_records.get_by_id_and_tenant(uuid.UUID(result.intake_record_id), tenant_id)
    assert record is not None
    assert record.status == IntakeRecordStatus.PROMOTED


class _BatchRun:
    """What the intake worker does with a stored batch: parse it, then process
    the records it produced with the same use case the single-lead path uses."""

    def __init__(self, uow: InMemoryUnitOfWork, commands: List[IngestLeadCommand]) -> None:
        self._uow = uow
        self._parse = ProcessBatchUseCase(uow=uow, file_parser=_StubFileParser(commands))
        self._process = ProcessIntakeJobUseCase(uow=uow, ingest=in_process_ingest(uow))

    def execute(self, tenant_id, job_id, file_content: bytes, filename: str) -> None:
        self._uow.intake_files.save(job_id, tenant_id, filename, file_content)
        self._parse.execute(tenant_id, job_id)
        self._process.execute(tenant_id, job_id)


def _batch_use_case(uow: InMemoryUnitOfWork, commands: List[IngestLeadCommand]) -> _BatchRun:
    return _BatchRun(uow, commands)


def test_batch_upload_promotes_the_valid_row_and_rejects_the_invalid_one():
    tenant_id = uuid.uuid4()
    source_id = uuid.uuid4()
    uow = _new_uow()
    job = uow.intake_jobs.save(IntakeJob.create(tenant_id=tenant_id, source_id=source_id, kind=IntakeJobKind.BATCH))

    commands = [
        _command(tenant_id=tenant_id, source_id=source_id, email="valid@example.com"),
        _command(tenant_id=tenant_id, source_id=source_id, email="not-an-email"),
    ]
    _batch_use_case(uow, commands).execute(
        tenant_id=tenant_id, job_id=job.id.value, file_content=b"irrelevant", filename="leads.csv",
    )

    saved_job = uow.intake_jobs.get_by_id_and_tenant(job.id.value, tenant_id)
    assert saved_job.status == IntakeJobStatus.COMPLETED
    assert saved_job.succeeded == 1
    assert saved_job.failed == 1

    records = uow.intake_records.list_by_tenant(tenant_id, job_id=job.id.value)
    assert len(records) == 2
    statuses = {r.status for r in records}
    assert statuses == {IntakeRecordStatus.PROMOTED, IntakeRecordStatus.REJECTED}


def test_batch_row_with_no_email_is_rejected_without_crashing_the_run():
    """Regression for the T4 Aviso 2 bug: a command's email can be None since
    T2, and the row must still land as a REJECTED record instead of raising
    partway through the run."""
    tenant_id = uuid.uuid4()
    source_id = uuid.uuid4()
    uow = _new_uow()
    job = uow.intake_jobs.save(IntakeJob.create(tenant_id=tenant_id, source_id=source_id, kind=IntakeJobKind.BATCH))

    # Fails on budget, not email: proves the crash this guards against was
    # about email being None, not about the row failing at all.
    commands = [_command(tenant_id=tenant_id, source_id=source_id, email=None, budget=-100.0)]
    _batch_use_case(uow, commands).execute(
        tenant_id=tenant_id, job_id=job.id.value, file_content=b"irrelevant", filename="leads.csv",
    )

    saved_job = uow.intake_jobs.get_by_id_and_tenant(job.id.value, tenant_id)
    assert saved_job.status == IntakeJobStatus.COMPLETED
    assert saved_job.failed == 1

    [record] = uow.intake_records.list_by_tenant(tenant_id, job_id=job.id.value)
    assert record.status == IntakeRecordStatus.REJECTED
    assert record.errors[0].error_code == "INVALID_BUDGET"
