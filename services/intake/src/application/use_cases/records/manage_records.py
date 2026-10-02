from uuid import UUID

from application.dtos.reception import IngestLeadCommand
from application.dtos.records import (
    GetIntakeRecordsQuery,
    IntakeRecordsPageResult,
    LeadProcessedResult,
    PromoteIntakeRecordCommand,
)
from application.ports.input.reception import IngestLeadInputPort
from application.ports.input.records import (
    DiscardIntakeRecordInputPort,
    GetIntakeRecordsInputPort,
    PromoteIntakeRecordInputPort,
)
from application.ports.output.admissions import AdmissionUnavailable
from application.ports.output.unit_of_work import UnitOfWorkPort
from domain.exceptions import DomainException
from domain.records.intake_record import IntakeRecord
from domain.value_objects.enums import IntakeRecordStatus


def _get_owned_record(uow: UnitOfWorkPort, tenant_id: UUID, record_id: UUID) -> IntakeRecord:
    """A record of another organization reads back as missing, never as a 403 that would confirm it exists."""
    record = uow.intake_records.get_by_id_and_tenant(record_id, tenant_id)
    if record is None:
        raise DomainException("The intake record does not exist", error_code="INTAKE_RECORD_NOT_FOUND")
    return record


class GetIntakeRecordsUseCase(GetIntakeRecordsInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, query: GetIntakeRecordsQuery) -> IntakeRecordsPageResult:
        status = None
        if query.status is not None:
            try:
                status = IntakeRecordStatus(query.status)
            except ValueError:
                raise DomainException(
                    f"Unknown intake record status: {query.status}", error_code="INVALID_INTAKE_STATUS",
                )
        with self.uow:
            items = self.uow.intake_records.list_by_tenant(
                query.tenant_id, status=status, job_id=query.job_id, limit=query.limit, offset=query.offset,
            )
            total = self.uow.intake_records.count_by_tenant(query.tenant_id, status=status, job_id=query.job_id)
        return IntakeRecordsPageResult(items=items, total=total)


class PromoteIntakeRecordUseCase(PromoteIntakeRecordInputPort):
    def __init__(self, uow: UnitOfWorkPort, ingest: IngestLeadInputPort) -> None:
        self.uow = uow
        self.ingest = ingest

    def execute(self, command: PromoteIntakeRecordCommand) -> LeadProcessedResult:
        with self.uow:
            record = _get_owned_record(self.uow, command.tenant_id, command.record_id)
            # Refused here: a manager promoting a record that already became a
            # lead is asking for something that cannot happen. Inside the
            # ingestion the same state means a lost race, answered idempotently.
            if record.status == IntakeRecordStatus.PROMOTED:
                raise DomainException(
                    f"Cannot promote an intake record from status {record.status.value}",
                    error_code="INVALID_INTAKE_TRANSITION",
                )

        payload = command.payload
        # Same pipeline as the first ingestion, over the channel the record
        # arrived on. The ingestion owns its own transactions and the
        # promote/reject transition: repeating either here would be a second one.
        ingest_command = IngestLeadCommand(
            tenant_id=command.tenant_id,
            source_id=record.source_id.value,
            first_name=payload.get("first_name", ""),
            last_name=payload.get("last_name", ""),
            email=payload.get("email"),
            company=payload.get("company", ""),
            budget=payload.get("budget"),
            industry=payload.get("industry", ""),
            custom_attributes=payload.get("custom_attributes") or {},
            phone=payload.get("phone"),
        )
        try:
            return self.ingest.execute(ingest_command, existing_record=record)
        except AdmissionUnavailable as exc:
            # Mapped here, not in the API, so every caller of the use case
            # sees the same stable error_code.
            raise DomainException(
                "The admission service is unavailable; try again shortly", error_code="LEAD_CORE_UNAVAILABLE",
            ) from exc


class DiscardIntakeRecordUseCase(DiscardIntakeRecordInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, tenant_id: UUID, record_id: UUID) -> None:
        with self.uow:
            # Locked like the worker's claim: a plain read could overwrite a
            # promotion committed in between, orphaning its lead.
            record = self.uow.intake_records.claim_unpromoted(record_id, tenant_id)
            if record is None:
                record = _get_owned_record(self.uow, tenant_id, record_id)
            record.discard()
            self.uow.intake_records.save(record)
