from uuid import uuid4

import pytest

from application.dtos.jobs import GetIntakeJobsQuery
from application.use_cases.jobs.manage_jobs import GetIntakeJobsUseCase, GetIntakeJobUseCase, ReprocessIntakeJobUseCase
from domain.exceptions import DomainException
from domain.jobs.intake_job import IntakeJob
from domain.value_objects.enums import IntakeJobKind, IntakeJobStatus
from tests.unit.application.doubles.uow import InMemoryUnitOfWork


def _job(uow, tenant_id, status=IntakeJobStatus.PENDING) -> IntakeJob:
    job = IntakeJob.create(tenant_id=tenant_id, source_id=uuid4(), kind=IntakeJobKind.BATCH)
    job.status = status
    return uow.intake_jobs.save(job)


def _code(action) -> str:
    with pytest.raises(DomainException) as caught:
        action()
    return caught.value.error_code


def test_reprocessing_resets_the_counters_and_queues_the_job_instead_of_running_it():
    uow, tenant_id = InMemoryUnitOfWork(), uuid4()
    job = _job(uow, tenant_id, IntakeJobStatus.PROCESSING)
    job.succeeded, job.failed = 3, 1

    ReprocessIntakeJobUseCase(uow).execute(tenant_id, job.id.value)

    assert (job.status, job.succeeded, job.failed) == (IntakeJobStatus.PENDING, 0, 0)
    [event] = uow.events("IntakeJobRequested")
    assert (event.channel, event.payload) == ("job", {"tenant_id": str(tenant_id), "job_id": str(job.id)})


@pytest.mark.parametrize("status", [IntakeJobStatus.COMPLETED, IntakeJobStatus.FAILED])
def test_a_finished_job_cannot_be_reprocessed(status):
    uow, tenant_id = InMemoryUnitOfWork(), uuid4()
    job = _job(uow, tenant_id, status)

    assert _code(lambda: ReprocessIntakeJobUseCase(uow).execute(tenant_id, job.id.value)) == "INVALID_JOB_TRANSITION"
    assert uow.events() == []


def test_a_job_of_another_organization_is_not_found():
    uow = InMemoryUnitOfWork()
    job = _job(uow, uuid4())

    assert _code(lambda: GetIntakeJobUseCase(uow).execute(uuid4(), job.id.value)) == "INTAKE_JOB_NOT_FOUND"
    assert _code(lambda: ReprocessIntakeJobUseCase(uow).execute(uuid4(), job.id.value)) == "INTAKE_JOB_NOT_FOUND"


def test_listing_filters_by_status_within_the_organization():
    uow, tenant_id = InMemoryUnitOfWork(), uuid4()
    _job(uow, tenant_id)
    _job(uow, tenant_id, IntakeJobStatus.COMPLETED)
    _job(uow, uuid4())

    page = GetIntakeJobsUseCase(uow).execute(GetIntakeJobsQuery(tenant_id=tenant_id, status="COMPLETED"))

    assert (len(page.items), page.total) == (1, 1)


def test_listing_by_an_unknown_status_is_a_domain_error():
    assert _code(lambda: GetIntakeJobsUseCase(InMemoryUnitOfWork()).execute(
        GetIntakeJobsQuery(tenant_id=uuid4(), status="NOPE"))) == "INVALID_JOB_STATUS"
