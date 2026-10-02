from uuid import UUID

from application.ports.input.reception import ProcessBatchInputPort
from application.ports.output.parsing import FileParserPort
from application.ports.output.unit_of_work import UnitOfWorkPort
from application.use_cases.reception.payloads import payload_of
from domain.exceptions import DomainException
from domain.records.intake_record import IntakeRecord


class ProcessBatchUseCase(ProcessBatchInputPort):
    """Turns the stored file of a batch job into its intake records.

    It only parses: deciding on the records is ProcessIntakeJobUseCase, run by
    the same worker right after."""

    def __init__(self, uow: UnitOfWorkPort, file_parser: FileParserPort) -> None:
        self.uow = uow
        self.file_parser = file_parser

    def execute(self, tenant_id: UUID, job_id: UUID) -> None:
        with self.uow:
            job = self.uow.intake_jobs.get_by_id_and_tenant(job_id, tenant_id)
            if job is None:
                raise DomainException("The intake job does not exist", error_code="INTAKE_JOB_NOT_FOUND")
            stored = self.uow.intake_files.get(job_id, tenant_id)
            # parsed_at, committed with the records, keeps a redelivered
            # message from materialising the file twice.
            if stored is None or stored.parsed_at is not None:
                return
            source_id = job.source_id.value
            try:
                commands = self.file_parser.parse_leads_file(stored.content, stored.filename, tenant_id, source_id)
            except Exception:
                # An unreadable file is a job that never started, not one with
                # failed items: there are no rows to record or reprocess.
                job.fail()
                self.uow.intake_jobs.save(job)
                return
            for command in commands:
                self.uow.intake_records.save(IntakeRecord.create(
                    tenant_id=tenant_id, source_id=source_id, job_id=job_id, payload=payload_of(command),
                ))
            job.set_total(len(commands))
            self.uow.intake_jobs.save(job)
            self.uow.intake_files.mark_parsed(job_id)
