from fastapi import APIRouter, Depends, status
from application.dtos.context import RequestContext
from application.dtos.queries import GetLeadsQuery
from application.ports.input.get_leads_use_case_port import GetLeadsInputPort
from infrastructure.adapters.input.api.dependencies import (
    get_get_leads_use_case,
    require_organization_manager,
)

from infrastructure.adapters.input.api.schemas import (
    LeadResponse,
    PaginatedLeadsResponse,
)

router = APIRouter()

@router.get("", response_model=PaginatedLeadsResponse, status_code=status.HTTP_200_OK)
@router.get("/", response_model=PaginatedLeadsResponse, status_code=status.HTTP_200_OK, include_in_schema=False)
def list_leads(
    limit: int = 100,
    offset: int = 0,
    # Manager-only, and deliberately not "authenticated org member": this
    # endpoint returns the whole organization's pipeline, so a sales agent
    # reaching it would read its colleagues' leads. The agent's own view is
    # GET /leads/mine, a separate endpoint rather than a role branch in here.
    context: RequestContext = Depends(require_organization_manager),
    use_case: GetLeadsInputPort = Depends(get_get_leads_use_case),
) -> PaginatedLeadsResponse:
    query = GetLeadsQuery(tenant_id=context.tenant_id, limit=limit, offset=offset)
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
