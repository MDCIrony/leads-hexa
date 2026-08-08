import uuid
from typing import List

from application.dtos.commands import IngestLeadCommand
from application.use_cases.ingest_lead_use_case import IngestLeadUseCase
from application.use_cases.process_batch_use_case import ProcessBatchUseCase
from domain.entities.lead_source import LeadSource
from domain.value_objects.enums import IntakeRecordStatus, LeadSourceKind
from infrastructure.adapters.input.api.schemas import FailedRowResponse
from tests.unit.mocks.in_memory_agent_repo import InMemoryAgentRepository
from tests.unit.mocks.in_memory_lead_repo import InMemoryLeadRepository
from tests.unit.mocks.in_memory_rule_repo import InMemoryRuleRepository
from tests.unit.mocks.in_memory_sales_group_repo import InMemorySalesGroupRepository
from tests.unit.mocks.in_memory_uow import InMemoryUnitOfWork


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
        InMemoryAgentRepository(),
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


def test_valid_payload_promotes_the_intake_record_to_the_created_lead():
    tenant_id = uuid.uuid4()
    uow = _new_uow()
    use_case = IngestLeadUseCase(uow=uow)

    result = use_case.execute(_command(tenant_id=tenant_id))

    assert result.error is None
    assert result.lead_id != ""
    record = uow.intake_records.get_by_id_and_tenant(uuid.UUID(result.intake_record_id), tenant_id)
    assert record is not None
    assert record.status == IntakeRecordStatus.PROMOTED
    assert str(record.lead_id) == result.lead_id


def test_invalid_email_rejects_the_intake_record_without_creating_a_lead():
    tenant_id = uuid.uuid4()
    uow = _new_uow()
    use_case = IngestLeadUseCase(uow=uow)

    result = use_case.execute(_command(tenant_id=tenant_id, email="not-an-email"))

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
    use_case = IngestLeadUseCase(uow=uow)

    result = use_case.execute(_command(tenant_id=tenant_id, email=None))

    assert result.error is None
    assert result.lead_id != ""
    record = uow.intake_records.get_by_id_and_tenant(uuid.UUID(result.intake_record_id), tenant_id)
    assert record is not None
    assert record.status == IntakeRecordStatus.PROMOTED


def test_batch_upload_promotes_the_valid_row_and_rejects_the_invalid_one():
    tenant_id = uuid.uuid4()
    source_id = uuid.uuid4()
    uow = _new_uow()
    # ProcessBatchUseCase now resolves FILE_UPLOAD's source_id itself.
    uow.sources.save(LeadSource.create(tenant_id=tenant_id, name="File upload", kind=LeadSourceKind.FILE_UPLOAD))
    ingest_use_case = IngestLeadUseCase(uow=uow)

    commands = [
        _command(tenant_id=tenant_id, source_id=source_id, email="valid@example.com"),
        _command(tenant_id=tenant_id, source_id=source_id, email="not-an-email"),
    ]
    batch_use_case = ProcessBatchUseCase(
        file_parser=_StubFileParser(commands),
        ingest_lead_use_case=ingest_use_case,
    )

    result = batch_use_case.execute(file_content=b"irrelevant", filename="leads.csv", tenant_id=tenant_id)

    assert result.successful_ingestions == 1
    assert len(result.failed_rows) == 1
    assert result.failed_rows[0].intake_record_id != ""

    records = uow.intake_records.list_by_tenant(tenant_id)
    assert len(records) == 2
    statuses = {r.status for r in records}
    assert statuses == {IntakeRecordStatus.PROMOTED, IntakeRecordStatus.REJECTED}


def test_batch_upload_failed_row_with_no_email_does_not_break_the_response_schema():
    """Regression for the T4 Aviso 2 bug: FailedRow.email carried a bare
    `str` while, since T2, a command's email can be None. The dataclass
    swallowed None silently, but FailedRowResponse (a pydantic model) used
    to raise ValidationError on it, turning a legitimate partial-success
    batch upload into an HTTP 500."""
    tenant_id = uuid.uuid4()
    source_id = uuid.uuid4()
    uow = _new_uow()
    # ProcessBatchUseCase now resolves FILE_UPLOAD's source_id itself.
    uow.sources.save(LeadSource.create(tenant_id=tenant_id, name="File upload", kind=LeadSourceKind.FILE_UPLOAD))
    ingest_use_case = IngestLeadUseCase(uow=uow)

    # Fails on budget, not email: proves the crash was about email being
    # None, not about the row failing at all.
    commands = [_command(tenant_id=tenant_id, source_id=source_id, email=None, budget=-100.0)]
    batch_use_case = ProcessBatchUseCase(
        file_parser=_StubFileParser(commands),
        ingest_lead_use_case=ingest_use_case,
    )

    result = batch_use_case.execute(file_content=b"irrelevant", filename="leads.csv", tenant_id=tenant_id)

    assert len(result.failed_rows) == 1
    failed = result.failed_rows[0]
    assert failed.email is None
    assert failed.error_code == "INVALID_BUDGET"

    # This construction is the line that used to raise pydantic.ValidationError.
    response = FailedRowResponse(
        row_number=failed.row_number,
        email=failed.email,
        error=failed.error,
        error_code=failed.error_code,
    )
    assert response.email is None
