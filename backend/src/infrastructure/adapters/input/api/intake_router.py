from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile, status
from fastapi.responses import JSONResponse
from application.dtos.commands import PromoteIntakeRecordCommand, ReceiveIntakeCommand
from application.dtos.context import RequestContext
from application.dtos.queries import GetIntakeRecordsQuery
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
from domain.entities.intake_record import IntakeRecord
from domain.value_objects.enums import IntakeJobKind, IntakeRecordStatus
from infrastructure.adapters.input.api.dependencies import (
    get_discard_intake_record_use_case,
    get_get_intake_records_use_case,
    get_process_batch_use_case,
    get_process_intake_job_use_case,
    get_promote_intake_record_use_case,
    get_receive_intake_use_case,
    require_organization_manager,
)

from infrastructure.adapters.input.api.schemas import (
    IngestLeadRequest,
    IntakeAcceptedResponse,
    IntakeErrorResponse,
    IntakeRecordResponse,
    IntakeRecordsPageResponse,
    LeadProcessedResponse,
    BatchProcessResponse,
    FailedRowResponse,
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

@router.post("/leads/batch-upload", response_model=BatchProcessResponse, status_code=status.HTTP_200_OK)
async def batch_upload(
    file: UploadFile = File(...),
    context: RequestContext = Depends(require_organization_manager),
    use_case: ProcessBatchInputPort = Depends(get_process_batch_use_case),
):
    content = await file.read()
    result = use_case.execute(
        file_content=content,
        filename=file.filename or "leads.csv",
        tenant_id=context.tenant_id,
    )
    return BatchProcessResponse(
        job_id=result.job_id,
        total_rows=result.total_rows,
        successful_ingestions=result.successful_ingestions,
        failed_rows=[
            FailedRowResponse(
                row_number=row.row_number,
                email=row.email,
                error=row.error,
                error_code=row.error_code,
                intake_record_id=row.intake_record_id,
            )
            for row in result.failed_rows
        ],
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
