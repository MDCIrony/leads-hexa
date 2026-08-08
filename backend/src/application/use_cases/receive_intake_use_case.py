from application.dtos.commands import ReceiveIntakeCommand, ReceiveIntakeResult
from application.ports.input.intake_phase_use_case_ports import ReceiveIntakeInputPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from domain.entities.intake_job import IntakeJob
from domain.entities.intake_record import IntakeRecord
from domain.exceptions import DomainException
from domain.value_objects.enums import IntakeJobKind, LeadSourceKind


class ReceiveIntakeUseCase(ReceiveIntakeInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, command: ReceiveIntakeCommand) -> ReceiveIntakeResult:
        kind = IntakeJobKind(command.kind)
        source_kind = (
            LeadSourceKind.MANUAL_FORM if kind == IntakeJobKind.SINGLE else LeadSourceKind.FILE_UPLOAD
        )
        with self.uow:
            source = self.uow.sources.get_by_kind(command.tenant_id, source_kind)
            if source is None:
                raise DomainException(
                    f"No active source of kind {source_kind.value} found for this organization",
                    error_code="SOURCE_NOT_FOUND",
                )
            job = self.uow.intake_jobs.save(IntakeJob.create(
                tenant_id=command.tenant_id,
                source_id=source.id.value,
                kind=kind,
                total_items=len(command.payloads) or None,
            ))
            records = [
                self.uow.intake_records.save(IntakeRecord.create(
                    tenant_id=command.tenant_id,
                    source_id=source.id.value,
                    job_id=job.id.value,
                    payload=payload,
                ))
                for payload in command.payloads
            ]
        return ReceiveIntakeResult(
            job_id=str(job.id),
            record_ids=[str(r.id) for r in records],
            status=job.status.value,
        )
