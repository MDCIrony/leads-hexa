from uuid import UUID
from typing import List
from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import JSONResponse
from application.dtos.commands import IngestLeadCommand
from application.dtos.queries import GetLeadsQuery
from application.ports.input.ingest_lead_use_case_port import IngestLeadInputPort
from application.ports.input.process_batch_use_case_port import ProcessBatchInputPort
from application.ports.input.get_leads_use_case_port import GetLeadsInputPort
from domain.entities.agent import Agent
from infrastructure.adapters.input.api.dependencies import (
    get_ingest_lead_use_case,
    get_process_batch_use_case,
    get_get_leads_use_case,
    verify_tenant_access,
)

from infrastructure.adapters.input.api.schemas import (
    IngestLeadRequest,
    LeadProcessedResponse,
    BatchProcessResponse,
    LeadResponse,
    PaginatedLeadsResponse,
)

router = APIRouter()

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
        failed_rows=result.failed_rows,
    )

@router.get("", response_model=PaginatedLeadsResponse, status_code=status.HTTP_200_OK)
@router.get("/", response_model=PaginatedLeadsResponse, status_code=status.HTTP_200_OK, include_in_schema=False)
def list_leads(
    tenant_id: UUID,
    limit: int = 100,
    offset: int = 0,
    use_case: GetLeadsInputPort = Depends(get_get_leads_use_case),
    current_agent: Agent = Depends(verify_tenant_access),
):

    query = GetLeadsQuery(tenant_id=tenant_id, limit=limit, offset=offset)
    page = use_case.execute(query)
    items = [
        LeadResponse(
            id=str(lead.id),
            tenant_id=str(lead.tenant_id),
            first_name=lead.first_name,
            last_name=lead.last_name,
            email=str(lead.email),
            company=lead.company,
            budget=float(lead.budget),
            industry=lead.industry,
            custom_attributes=lead.custom_attributes,
            phone=lead.phone,
            score=int(lead.score),
            status=lead.status.value,
            assigned_agent_id=str(lead.assigned_agent_id) if lead.assigned_agent_id else None,
            created_at=lead.created_at.isoformat(),
        )
        for lead in page.items
    ]
    return PaginatedLeadsResponse(
        items=items,
        total=page.total,
        limit=limit,
        offset=offset,
        has_more=(offset + len(items)) < page.total,
    )

