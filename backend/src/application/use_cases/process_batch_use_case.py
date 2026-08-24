from typing import Optional
from uuid import UUID

from application.ports.input.intake_phase_use_case_ports import ProcessIntakeJobInputPort
from application.ports.input.process_batch_use_case_port import ProcessBatchInputPort
from application.ports.output.file_parser_port import FileParserPort
from application.ports.output.job_queue_port import JobQueuePort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from application.use_cases.ingest_lead_use_case import payload_of
from domain.entities.intake_record import IntakeRecord
from domain.exceptions import DomainException


class ProcessBatchUseCase(ProcessBatchInputPort):
    def __init__(
        self,
        uow: UnitOfWorkPort,
        file_parser: FileParserPort,
        process_job: ProcessIntakeJobInputPort,
        job_queue: Optional[JobQueuePort] = None,
    ) -> None:
        self.uow = uow
        self.file_parser = file_parser
        self.process_job = process_job
        self.job_queue = job_queue

    def execute(self, tenant_id: UUID, job_id: UUID, file_content: bytes, filename: str) -> None:
        with self.uow:
            job = self.uow.intake_jobs.get_by_id_and_tenant(job_id, tenant_id)
            if job is None:
                raise DomainException("The intake job does not exist", error_code="INTAKE_JOB_NOT_FOUND")
            source_id = job.source_id.value

        try:
            commands = self.file_parser.parse_leads_file(file_content, filename, tenant_id, source_id)
        except Exception:
            # An unreadable file is a job that never got to start, not one with
            # failed items: there are no rows to record or to reprocess.
            with self.uow:
                job = self.uow.intake_jobs.get_by_id_and_tenant(job_id, tenant_id)
                job.fail()
                self.uow.intake_jobs.save(job)
            return

        with self.uow:
            job = self.uow.intake_jobs.get_by_id_and_tenant(job_id, tenant_id)
            for command in commands:
                self.uow.intake_records.save(IntakeRecord.create(
                    tenant_id=tenant_id,
                    source_id=source_id,
                    job_id=job_id,
                    payload=payload_of(command),
                ))
            job.set_total(len(commands))
            self.uow.intake_jobs.save(job)

        # Parsing the file needs its bytes and so has to happen here, but the
        # long half — scoring and routing ten thousand rows — is what actually
        # dies with the process, and by now every row is a durable record a
        # worker can pick up from its id alone. Same fallback as the
        # single-lead endpoint: a broker that is down means doing the work
        # here, not dropping the customer's file.
        if self.job_queue is None or not self.job_queue.enqueue_intake_job(tenant_id, job_id):
            self.process_job.execute(tenant_id, job_id)
