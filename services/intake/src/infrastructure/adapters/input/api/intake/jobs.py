from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from application.dtos.context import RequestContext
from application.dtos.jobs import GetIntakeJobsQuery
from application.ports.input.jobs import GetIntakeJobInputPort, GetIntakeJobsInputPort, ReprocessIntakeJobInputPort
from domain.jobs.intake_job import IntakeJob
from infrastructure.adapters.input.api.dependencies import require_organization_manager
from infrastructure.adapters.input.api.intake.schemas import IntakeJobResponse, IntakeJobsPageResponse
from infrastructure.adapters.input.api.use_case_factories import (
    get_get_intake_job_use_case,
    get_get_intake_jobs_use_case,
    get_reprocess_intake_job_use_case,
)

router = APIRouter()


def _to_job_response(job: IntakeJob) -> IntakeJobResponse:
    return IntakeJobResponse(
        id=str(job.id),
        source_id=str(job.source_id),
        kind=job.kind.value,
        status=job.status.value,
        total_items=job.total_items,
        succeeded=job.succeeded,
        failed=job.failed,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )


@router.get("/jobs", response_model=IntakeJobsPageResponse, status_code=status.HTTP_200_OK)
def list_intake_jobs(
    status: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    context: RequestContext = Depends(require_organization_manager),
    use_case: GetIntakeJobsInputPort = Depends(get_get_intake_jobs_use_case),
):
    page = use_case.execute(GetIntakeJobsQuery(tenant_id=context.tenant_id, status=status, limit=limit, offset=offset))
    items = [_to_job_response(job) for job in page.items]
    return IntakeJobsPageResponse(
        items=items, total=page.total, limit=limit, offset=offset, has_more=(offset + len(items)) < page.total,
    )


@router.get("/jobs/{job_id}", response_model=IntakeJobResponse, status_code=status.HTTP_200_OK)
def get_intake_job(
    job_id: UUID,
    context: RequestContext = Depends(require_organization_manager),
    use_case: GetIntakeJobInputPort = Depends(get_get_intake_job_use_case),
):
    return _to_job_response(use_case.execute(context.tenant_id, job_id))


@router.post("/jobs/{job_id}/reprocess", response_model=IntakeJobResponse, status_code=status.HTTP_202_ACCEPTED)
def reprocess_intake_job(
    job_id: UUID,
    context: RequestContext = Depends(require_organization_manager),
    reprocess: ReprocessIntakeJobInputPort = Depends(get_reprocess_intake_job_use_case),
    get_job: GetIntakeJobInputPort = Depends(get_get_intake_job_use_case),
):
    # The checks run here so an unowned or finished job is a clean 404/400; the
    # run itself is queued, and the job comes back as it now stands.
    reprocess.execute(context.tenant_id, job_id)
    return _to_job_response(get_job.execute(context.tenant_id, job_id))
