from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from application.dtos.commands import PromoteIntakeRecordCommand, ReceiveIntakeCommand
from application.dtos.context import RequestContext
from application.dtos.queries import GetIntakeJobsQuery, GetIntakeRecordsQuery
from application.ports.input.intake_job_use_case_ports import (
    GetIntakeJobInputPort,
    GetIntakeJobsInputPort,
    ReprocessIntakeJobInputPort,
)
from application.ports.input.intake_phase_use_case_ports import ReceiveIntakeInputPort
from application.ports.input.intake_record_use_case_ports import (
    DiscardIntakeRecordInputPort,
    GetIntakeRecordsInputPort,
    PromoteIntakeRecordInputPort,
)
from domain.entities.intake_job import IntakeJob
from domain.entities.intake_record import IntakeRecord
from domain.value_objects.enums import IntakeJobKind, IntakeRecordStatus
from infrastructure.adapters.input.api.dependencies import (
    get_discard_intake_record_use_case,
    get_get_intake_job_use_case,
    get_get_intake_jobs_use_case,
    get_get_intake_records_use_case,
    get_promote_intake_record_use_case,
    get_receive_intake_use_case,
    get_reprocess_intake_job_use_case,
    require_organization_manager,
)
from infrastructure.adapters.input.api.schemas import (
    IngestLeadRequest,
    IntakeAcceptedResponse,
    IntakeErrorResponse,
    IntakeJobResponse,
    IntakeJobsPageResponse,
    IntakeRecordResponse,
    IntakeRecordsPageResponse,
    LeadProcessedResponse,
    PromoteIntakeRecordRequest,
)

router = APIRouter()

# The gateway's limit too, repeated here because the backend must hold it on
# its own when called without the gateway in front.
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _to_record_response(record: IntakeRecord) -> IntakeRecordResponse:
    return IntakeRecordResponse(
        id=str(record.id),
        source_id=str(record.source_id),
        status=record.status.value,
        payload=record.payload,
        errors=[
            IntakeErrorResponse(
                field=error.field,
                message=error.message,
                received_value=error.received_value,
                error_code=error.error_code,
            )
            for error in record.errors
        ],
        received_at=record.received_at,
        processed_at=record.processed_at,
        lead_id=str(record.lead_id) if record.lead_id else None,
    )

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

@router.post("/leads/ingest", response_model=IntakeAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
def ingest_lead(
    request: IngestLeadRequest,
    context: RequestContext = Depends(require_organization_manager),
    receive: ReceiveIntakeInputPort = Depends(get_receive_intake_use_case),
):
    # Reception records the job in the outbox in the same transaction as the
    # record; the relay hands it to RabbitMQ, so a broker outage only delays it.
    received = receive.execute(ReceiveIntakeCommand(
        tenant_id=context.tenant_id,
        kind=IntakeJobKind.SINGLE.value,
        payloads=[request.model_dump()],
    ))
    return IntakeAcceptedResponse(
        job_id=received.job_id,
        record_ids=received.record_ids,
        status=received.status,
    )

@router.post("/leads/batch-upload", response_model=IntakeAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
async def batch_upload(
    file: UploadFile = File(...),
    context: RequestContext = Depends(require_organization_manager),
    receive: ReceiveIntakeInputPort = Depends(get_receive_intake_use_case),
):
    # One byte past the limit is enough to know, without reading the rest.
    content = await file.read(_MAX_UPLOAD_BYTES + 1)
    if len(content) > _MAX_UPLOAD_BYTES:
        return JSONResponse(
            status_code=413,
            content={"error": True, "error_code": "PAYLOAD_TOO_LARGE", "message": "Request body too large"},
        )
    # Stored with the job (the file must outlive this process), and off the
    # event loop: up to 10 MB of bytea is a blocking write.
    received = await run_in_threadpool(receive.execute, ReceiveIntakeCommand(
        tenant_id=context.tenant_id,
        kind=IntakeJobKind.BATCH.value,
        payloads=[],
        filename=file.filename,
        content=content,
    ))
    return IntakeAcceptedResponse(
        job_id=received.job_id,
        record_ids=[],
        status=received.status,
    )

@router.get("/records", response_model=IntakeRecordsPageResponse, status_code=status.HTTP_200_OK)
def list_intake_records(
    status: Optional[str] = None,
    job_id: Optional[UUID] = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    context: RequestContext = Depends(require_organization_manager),
    use_case: GetIntakeRecordsInputPort = Depends(get_get_intake_records_use_case),
):
    query = GetIntakeRecordsQuery(
        tenant_id=context.tenant_id, status=status, job_id=job_id, limit=limit, offset=offset,
    )
    page = use_case.execute(query)
    items = [_to_record_response(record) for record in page.items]
    return IntakeRecordsPageResponse(
        items=items,
        total=page.total,
        limit=limit,
        offset=offset,
        has_more=(offset + len(items)) < page.total,
    )

@router.post("/records/{record_id}/promote", response_model=LeadProcessedResponse, status_code=status.HTTP_200_OK)
def promote_intake_record(
    record_id: UUID,
    request: PromoteIntakeRecordRequest,
    context: RequestContext = Depends(require_organization_manager),
    use_case: PromoteIntakeRecordInputPort = Depends(get_promote_intake_record_use_case),
):
    command = PromoteIntakeRecordCommand(
        tenant_id=context.tenant_id,
        record_id=record_id,
        payload=request.payload,
    )
    result = use_case.execute(command)

    if result.status == IntakeRecordStatus.REJECTED.value:
        # Same reasoning as the ingest endpoint above: a retry that fails
        # again is a bad request, not a 200 — and nothing is lost either way,
        # since IngestLeadUseCase already re-saved the record as REJECTED
        # with its new errors before returning.
        return JSONResponse(
            status_code=400,
            content={
                "error": True,
                "error_code": result.error_code,
                "message": result.error,
                "intake_record_id": result.intake_record_id,
            },
        )

    return LeadProcessedResponse(
        lead_id=result.lead_id,
        status=result.status,
        score=result.score,
        assigned_agent_id=result.assigned_agent_id,
        applied_rules_count=result.applied_rules_count,
        error=result.error,
        error_code=result.error_code,
        intake_record_id=result.intake_record_id,
    )

@router.post("/records/{record_id}/discard", status_code=status.HTTP_204_NO_CONTENT)
def discard_intake_record(
    record_id: UUID,
    context: RequestContext = Depends(require_organization_manager),
    use_case: DiscardIntakeRecordInputPort = Depends(get_discard_intake_record_use_case),
):
    use_case.execute(tenant_id=context.tenant_id, record_id=record_id)

# Literal route declared before the parametric one below, so a future
# sibling literal under /jobs can never be shadowed by {job_id}.
@router.get("/jobs", response_model=IntakeJobsPageResponse, status_code=status.HTTP_200_OK)
def list_intake_jobs(
    status: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    context: RequestContext = Depends(require_organization_manager),
    use_case: GetIntakeJobsInputPort = Depends(get_get_intake_jobs_use_case),
):
    query = GetIntakeJobsQuery(tenant_id=context.tenant_id, status=status, limit=limit, offset=offset)
    page = use_case.execute(query)
    items = [_to_job_response(job) for job in page.items]
    return IntakeJobsPageResponse(
        items=items,
        total=page.total,
        limit=limit,
        offset=offset,
        has_more=(offset + len(items)) < page.total,
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
    # The checks run here so an unowned or finished job is a clean 404/400;
    # the run itself is queued, and the job comes back as it now stands.
    reprocess.execute(context.tenant_id, job_id)
    return _to_job_response(get_job.execute(context.tenant_id, job_id))
