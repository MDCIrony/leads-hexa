from uuid import UUID

from application.dtos.commands import (
    IngestLeadCommand,
    IntakeRecordsPageResult,
    LeadProcessedResult,
    PromoteIntakeRecordCommand,
)
from application.dtos.queries import GetIntakeRecordsQuery
from application.ports.input.ingest_lead_use_case_port import IngestLeadInputPort
from application.ports.input.intake_record_use_case_ports import (
    DiscardIntakeRecordInputPort,
    GetIntakeRecordsInputPort,
    PromoteIntakeRecordInputPort,
)
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from domain.entities.intake_record import IntakeRecord
from domain.exceptions import DomainException
from domain.value_objects.enums import IntakeRecordStatus


def _get_owned_record(uow: UnitOfWorkPort, tenant_id: UUID, record_id: UUID) -> IntakeRecord:
    """A record from another organization must read back as missing, never as
    a 403 that would confirm it exists elsewhere."""
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
                    f"Unknown intake record status: {query.status}",
                    error_code="INVALID_INTAKE_STATUS",
                )
        with self.uow:
            items = self.uow.intake_records.list_by_tenant(
                query.tenant_id, status=status, job_id=query.job_id,
                limit=query.limit, offset=query.offset,
            )
            total = self.uow.intake_records.count_by_tenant(
                query.tenant_id, status=status, job_id=query.job_id,
            )
        return IntakeRecordsPageResult(items=items, total=total)


class PromoteIntakeRecordUseCase(PromoteIntakeRecordInputPort):
    def __init__(self, uow: UnitOfWorkPort, ingest: IngestLeadInputPort) -> None:
        self.uow = uow
        self.ingest = ingest

    def execute(self, command: PromoteIntakeRecordCommand) -> LeadProcessedResult:
        with self.uow:
            record = _get_owned_record(self.uow, command.tenant_id, command.record_id)
            # Refused here rather than deeper down: a manager promoting a
            # record that already became a lead is asking for something that
            # cannot happen, and deserves to be told. Downstream the same
            # situation means something else entirely — a run that lost a race
            # to a concurrent one — and there it is answered idempotently.
            if record.status == IntakeRecordStatus.PROMOTED:
                raise DomainException(
                    f"Cannot promote an intake record from status {record.status.value}",
                    error_code="INVALID_INTAKE_TRANSITION",
                )

        # Same pipeline as first ingestion, over the channel the lead actually
        # arrived on (record.source_id) rather than one resolved fresh here.
        # IngestLeadUseCase manages its own transaction and its own
        # promote()/reject() calls on `record` — calling either one here too
        # would be a second transition on what could already be terminal.
        ingest_command = IngestLeadCommand(
            tenant_id=command.tenant_id,
            source_id=record.source_id.value,
            first_name=command.payload.get("first_name", ""),
            last_name=command.payload.get("last_name", ""),
            email=command.payload.get("email"),
            company=command.payload.get("company", ""),
            budget=command.payload.get("budget"),
            industry=command.payload.get("industry", ""),
            custom_attributes=command.payload.get("custom_attributes") or {},
            phone=command.payload.get("phone"),
        )
        return self.ingest.execute(ingest_command, existing_record=record)


class DiscardIntakeRecordUseCase(DiscardIntakeRecordInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, tenant_id: UUID, record_id: UUID) -> None:
        with self.uow:
            record = _get_owned_record(self.uow, tenant_id, record_id)
            record.discard()
            self.uow.intake_records.save(record)
