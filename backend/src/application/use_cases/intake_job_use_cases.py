from uuid import UUID

from application.dtos.commands import IntakeJobsPageResult
from application.dtos.queries import GetIntakeJobsQuery
from application.ports.input.intake_job_use_case_ports import (
    GetIntakeJobInputPort,
    GetIntakeJobsInputPort,
    ReprocessIntakeJobInputPort,
)
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from domain.entities.intake_job import IntakeJob
from domain.events.intake_events import IntakeJobRequested
from domain.exceptions import DomainException
from domain.value_objects.enums import IntakeJobStatus


def _get_owned_job(uow: UnitOfWorkPort, tenant_id: UUID, job_id: UUID) -> IntakeJob:
    """A job from another organization must read back as missing, never as a
    403 that would confirm it exists elsewhere."""
    job = uow.intake_jobs.get_by_id_and_tenant(job_id, tenant_id)
    if job is None:
        raise DomainException("The intake job does not exist", error_code="INTAKE_JOB_NOT_FOUND")
    return job


class GetIntakeJobsUseCase(GetIntakeJobsInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, query: GetIntakeJobsQuery) -> IntakeJobsPageResult:
        status = None
        if query.status is not None:
            try:
                status = IntakeJobStatus(query.status)
            except ValueError:
                raise DomainException(
                    f"Unknown intake job status: {query.status}",
                    error_code="INVALID_JOB_STATUS",
                )
        with self.uow:
            items = self.uow.intake_jobs.list_by_tenant(
                query.tenant_id, status=status, limit=query.limit, offset=query.offset,
            )
            total = self.uow.intake_jobs.count_by_tenant(query.tenant_id, status=status)
        return IntakeJobsPageResult(items=items, total=total)


class GetIntakeJobUseCase(GetIntakeJobInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, tenant_id: UUID, job_id: UUID) -> IntakeJob:
        with self.uow:
            return _get_owned_job(self.uow, tenant_id, job_id)


class ReprocessIntakeJobUseCase(ReprocessIntakeJobInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, tenant_id: UUID, job_id: UUID) -> None:
        with self.uow:
            job = _get_owned_job(self.uow, tenant_id, job_id)
            if job.status in (IntakeJobStatus.COMPLETED, IntakeJobStatus.FAILED):
                raise DomainException(
                    "A finished job cannot be reprocessed",
                    error_code="INVALID_JOB_TRANSITION",
                )
            # Counters reset: the run is about to re-count the same items, and
            # summing them twice would produce impossible totals.
            job.reset_counters()
            self.uow.intake_jobs.save(job)
            # Handed to a worker like any received job, never run in the
            # request: a 10k-record run must not hold an HTTP worker hostage.
            self.uow.outbox.record(
                IntakeJobRequested(tenant_id=str(tenant_id), job_id=str(job_id)), channel="job",
            )
