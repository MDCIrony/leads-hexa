from uuid import UUID
from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import JSONResponse
from application.dtos.commands import IngestLeadCommand
from application.ports.input.ingest_lead_use_case_port import IngestLeadInputPort
from application.ports.input.process_batch_use_case_port import ProcessBatchInputPort
from infrastructure.adapters.input.api.dependencies import (
    get_ingest_lead_use_case,
    get_process_batch_use_case,
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
):
    command = IngestLeadCommand(
        tenant_id=tenant_id,
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

    if result.status == "FAILED":
        # A row-level domain validation failure on the single-ingest path is a
        # transport-level bad request, not a 201 "processed but rejected" body.
        # The same use case is also called per-row from the batch upload path,
        # where a FAILED result is a legitimate partial-success outcome — that
        # path is untouched and keeps reading result.error/result.error_code directly.
        return JSONResponse(
            status_code=400,
            content={
                "error": True,
                "error_code": result.error_code,
                "message": result.error,
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
):
    content = await file.read()
    result = use_case.execute(
        file_content=content,
        filename=file.filename or "leads.csv",
        tenant_id=tenant_id,
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
