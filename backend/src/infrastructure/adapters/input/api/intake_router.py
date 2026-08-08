from uuid import UUID
from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import JSONResponse
from application.dtos.commands import IngestLeadCommand
from application.ports.input.ingest_lead_use_case_port import IngestLeadInputPort
from application.ports.input.process_batch_use_case_port import ProcessBatchInputPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from domain.value_objects.enums import IntakeRecordStatus, LeadSourceKind
from infrastructure.adapters.input.api.dependencies import (
    get_ingest_lead_use_case,
    get_process_batch_use_case,
    get_uow,
)

from infrastructure.adapters.input.api.schemas import (
    IngestLeadRequest,
    LeadProcessedResponse,
    BatchProcessResponse,
    FailedRowResponse,
)

router = APIRouter()

# Unauthenticated by design until F2 introduces LeadSource credentials.
# Tracked in docs/specs/2026-08-07-lead-router-mvp-design.md §8.
@router.post("/ingest", response_model=LeadProcessedResponse, status_code=status.HTTP_201_CREATED)
def ingest_lead(
    tenant_id: UUID,
    request: IngestLeadRequest,
    use_case: IngestLeadInputPort = Depends(get_ingest_lead_use_case),
    uow: UnitOfWorkPort = Depends(get_uow),
):
    # Resolved here only until T5 moves this into the use case itself; every
    # tenant gets a MANUAL_FORM source automatically at creation (CreateTenantUseCase).
    with uow:
        source = uow.sources.get_by_kind(tenant_id, LeadSourceKind.MANUAL_FORM)

    command = IngestLeadCommand(
        tenant_id=tenant_id,
        source_id=source.id.value,
        first_name=request.first_name,
        last_name=request.last_name,
        email=request.email,
        company=request.company,
        budget=request.budget,
        industry=request.industry,
        custom_attributes=request.custom_attributes,
        phone=request.phone,
    )
    result = use_case.execute(command)

    if result.status == IntakeRecordStatus.REJECTED.value:
        # A row-level domain validation failure on the single-ingest path is a
        # transport-level bad request, not a 201 "processed but rejected" body:
        # the manager filling the form needs to see the failure immediately.
        # The payload isn't lost either way — IngestLeadUseCase persists it as
        # a REJECTED IntakeRecord before returning — so refusing to pretend
        # success here costs nothing. The same use case is also called
        # per-row from the batch upload path, where a REJECTED result is a
        # legitimate partial-success outcome — that path is untouched and
        # keeps reading result.error/result.error_code directly.
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
    )

# Unauthenticated by design until F2 introduces LeadSource credentials.
# Tracked in docs/specs/2026-08-07-lead-router-mvp-design.md §8.
@router.post("/batch-upload", response_model=BatchProcessResponse, status_code=status.HTTP_200_OK)
async def batch_upload(
    tenant_id: UUID,
    file: UploadFile = File(...),
    use_case: ProcessBatchInputPort = Depends(get_process_batch_use_case),
    uow: UnitOfWorkPort = Depends(get_uow),
):
    with uow:
        source = uow.sources.get_by_kind(tenant_id, LeadSourceKind.FILE_UPLOAD)

    content = await file.read()
    result = use_case.execute(
        file_content=content,
        filename=file.filename or "leads.csv",
        tenant_id=tenant_id,
        source_id=source.id.value,
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
            )
            for row in result.failed_rows
        ],
    )
