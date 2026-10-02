from application.dtos.reception import ReceiveIntakeCommand, ReceiveIntakeResult
from application.ports.input.reception import ReceiveIntakeInputPort
from application.ports.output.unit_of_work import UnitOfWorkPort
from domain.events.intake_events import IntakeJobRequested
from domain.exceptions import DomainException
from domain.jobs.intake_job import IntakeJob
from domain.records.intake_record import IntakeRecord
from domain.value_objects.enums import IntakeJobKind, LeadSourceKind


class ReceiveIntakeUseCase(ReceiveIntakeInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, command: ReceiveIntakeCommand) -> ReceiveIntakeResult:
        kind = IntakeJobKind(command.kind)
        source_kind = LeadSourceKind.MANUAL_FORM if kind == IntakeJobKind.SINGLE else LeadSourceKind.FILE_UPLOAD
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
            if command.content is not None:
                self.uow.intake_files.save(
                    job.id.value, command.tenant_id, command.filename or "leads.csv", command.content,
                )
            # Same transaction as the job: a broker that is down delays the
            # work instead of losing it, and a rolled-back reception never
            # reaches a worker.
            self.uow.outbox.record(
                IntakeJobRequested(tenant_id=str(command.tenant_id), job_id=str(job.id)), channel="job",
            )
        return ReceiveIntakeResult(
            job_id=str(job.id),
            record_ids=[str(r.id) for r in records],
            status=job.status.value,
        )
