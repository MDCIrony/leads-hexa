from uuid import UUID
from typing import List
from fastapi import APIRouter, Depends, File, UploadFile, status
from application.dtos.commands import IngestLeadCommand
from application.ports.input.ingest_lead_use_case_port import IngestLeadInputPort
from application.ports.input.process_batch_use_case_port import ProcessBatchInputPort
from application.ports.output.lead_repository_port import LeadRepositoryPort
from infrastructure.adapters.input.api.dependencies import (
    get_ingest_lead_use_case,
    get_process_batch_use_case,
    get_lead_repo,
)
from infrastructure.adapters.input.api.schemas import (
    IngestLeadRequest,
    LeadProcessedResponse,
    BatchProcessResponse,
    LeadResponse,
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
    return LeadProcessedResponse(
        lead_id=result.lead_id,
        status=result.status,
        score=result.score,
        assigned_agent_id=result.assigned_agent_id,
        applied_rules_count=result.applied_rules_count,
        webhook_dispatched=result.webhook_dispatched,
        error=result.error,
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

@router.get("", response_model=List[LeadResponse], status_code=status.HTTP_200_OK)
@router.get("/", response_model=List[LeadResponse], status_code=status.HTTP_200_OK, include_in_schema=False)
def list_leads(
    tenant_id: UUID,
    limit: int = 100,
    offset: int = 0,
    lead_repo: LeadRepositoryPort = Depends(get_lead_repo),
):
    leads = lead_repo.list_by_tenant(tenant_id, limit=limit, offset=offset)
    return [
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
        for lead in leads
    ]
