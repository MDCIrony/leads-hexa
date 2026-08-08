from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile, status
from fastapi.responses import JSONResponse
from application.dtos.commands import PromoteIntakeRecordCommand, ReceiveIntakeCommand
from application.dtos.context import RequestContext
from application.dtos.queries import GetIntakeJobsQuery, GetIntakeRecordsQuery
from application.ports.input.intake_job_use_case_ports import (
    GetIntakeJobInputPort,
    GetIntakeJobsInputPort,
    ReprocessIntakeJobInputPort,
)
from application.ports.input.intake_phase_use_case_ports import (
    ProcessIntakeJobInputPort,
    ReceiveIntakeInputPort,
)
from application.ports.input.intake_record_use_case_ports import (
    DiscardIntakeRecordInputPort,
    GetIntakeRecordsInputPort,
    PromoteIntakeRecordInputPort,
)
from application.ports.input.process_batch_use_case_port import ProcessBatchInputPort
from domain.entities.intake_job import IntakeJob
from domain.entities.intake_record import IntakeRecord
from domain.value_objects.enums import IntakeJobKind, IntakeRecordStatus
from infrastructure.adapters.input.api.dependencies import (
    get_discard_intake_record_use_case,
    get_get_intake_job_use_case,
    get_get_intake_jobs_use_case,
    get_get_intake_records_use_case,
    get_process_batch_use_case,
    get_process_intake_job_use_case,
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
    background: BackgroundTasks,
    context: RequestContext = Depends(require_organization_manager),
    receive: ReceiveIntakeInputPort = Depends(get_receive_intake_use_case),
    process: ProcessIntakeJobInputPort = Depends(get_process_intake_job_use_case),
):
    received = receive.execute(ReceiveIntakeCommand(
        tenant_id=context.tenant_id,
        kind=IntakeJobKind.SINGLE.value,
        payloads=[request.model_dump()],
    ))
    # Queued after reception has confirmed: if the process dies here, the
    # record is already durable and the job stays visible to reprocess.
    background.add_task(process.execute, context.tenant_id, UUID(received.job_id))
    return IntakeAcceptedResponse(
        job_id=received.job_id,
        record_ids=received.record_ids,
        status=received.status,
    )

@router.post("/leads/batch-upload", response_model=IntakeAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
async def batch_upload(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    context: RequestContext = Depends(require_organization_manager),
    receive: ReceiveIntakeInputPort = Depends(get_receive_intake_use_case),
    process_batch: ProcessBatchInputPort = Depends(get_process_batch_use_case),
):
    # Read here, not inside the background task: the uploaded file closes
    # when the request ends, and the task has not run yet by then.
    content = await file.read()
    received = receive.execute(ReceiveIntakeCommand(
        tenant_id=context.tenant_id,
        kind=IntakeJobKind.BATCH.value,
        payloads=[],
    ))
    background.add_task(
        process_batch.execute,
        context.tenant_id, UUID(received.job_id), content, file.filename or "leads.csv",
    )
    return IntakeAcceptedResponse(
        job_id=received.job_id,
        record_ids=[],
        status=received.status,
    )

@router.get("/records", response_model=IntakeRecordsPageResponse, status_code=status.HTTP_200_OK)
def list_intake_records(
    status: Optional[str] = None,
    job_id: Optional[UUID] = None,
    limit: int = 100,
    offset: int = 0,
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
        webhook_dispatched=result.webhook_dispatched,
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
    limit: int = 100,
    offset: int = 0,
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
    # Not backgrounded, unlike ingest: Starlette has already started sending
    # the response by the time a background task runs, so a DomainException
    # raised in there (unowned job, already-terminal job) cannot become a
    # clean 404/400 anymore — it surfaces as a bare RuntimeError instead.
    # Running synchronously keeps the ownership/transition checks inside the
    # normal exception-handling path, and the work itself stays bounded by
    # the same _MAX_ITEMS_PER_RUN cap regular processing uses.
    reprocess.execute(context.tenant_id, job_id)
    return _to_job_response(get_job.execute(context.tenant_id, job_id))
