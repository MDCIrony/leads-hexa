from uuid import UUID

from application.ports.input.ingest_lead_use_case_port import IngestLeadInputPort
from application.ports.input.intake_phase_use_case_ports import ProcessIntakeJobInputPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from application.use_cases.intake.payloads import command_from_record
from domain.exceptions import DomainException
from domain.value_objects.enums import IntakeRecordStatus

# A single run takes at most this many items. Beyond it the rest stay PENDING
# and a second reprocess picks them up, because only PENDING records are read.
_MAX_ITEMS_PER_RUN = 10_000


class ProcessIntakeJobUseCase(ProcessIntakeJobInputPort):
    def __init__(self, uow: UnitOfWorkPort, ingest: IngestLeadInputPort) -> None:
        self.uow = uow
        self.ingest = ingest

    def execute(self, tenant_id: UUID, job_id: UUID) -> bool:
        with self.uow:
            job = self.uow.intake_jobs.get_by_id_and_tenant(job_id, tenant_id)
            if job is None:
                raise DomainException("The intake job does not exist", error_code="INTAKE_JOB_NOT_FOUND")
            job.start()
            self.uow.intake_jobs.save(job)
            pending = self.uow.intake_records.list_by_tenant(
                tenant_id,
                status=IntakeRecordStatus.PENDING,
                job_id=job_id,
                limit=_MAX_ITEMS_PER_RUN,
            )

        interrupted = False
        for record in pending:
            try:
                self.ingest.execute(command_from_record(record), existing_record=record)
            except Exception:
                # The record stays PENDING on purpose: it is the only state
                # reprocessing reads, so a failure here is recoverable instead
                # of lost. It is therefore not counted as failed either — it
                # has not failed, it is still pending.
                interrupted = True
                continue

        with self.uow:
            # Counted off the records, not accumulated while looping: the
            # records are what survives a process that dies mid-run, and two
            # consumers of a redelivered message reach the same number.
            job.set_counters(
                succeeded=self.uow.intake_records.count_by_tenant(
                    tenant_id, status=IntakeRecordStatus.PROMOTED, job_id=job_id
                ),
                failed=self.uow.intake_records.count_by_tenant(
                    tenant_id, status=IntakeRecordStatus.REJECTED, job_id=job_id
                ),
            )
            # An interrupted run does NOT complete: a COMPLETED job refuses
            # reprocessing, which would strand its PENDING records forever.
            if not interrupted:
                job.complete()
            self.uow.intake_jobs.save(job)
        return interrupted
