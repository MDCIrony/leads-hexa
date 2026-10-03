from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from application.dtos.leads import AssignLeadCommand, DiscardLeadCommand, GetLeadQuery, GetLeadStatsQuery, GetLeadsQuery, GetMyLeadsQuery
from application.dtos.context import RequestContext
from application.ports.input.leads.get_leads_use_case_port import GetLeadsInputPort
from application.ports.input.leads.get_lead_stats_use_case_port import GetLeadStatsInputPort
from application.ports.input.leads.lead_lifecycle_use_case_ports import (
    AssignLeadInputPort, DiscardLeadInputPort, GetLeadInputPort, GetMyLeadsInputPort,
)
from domain.exceptions import DomainException
from domain.policies.authorization_policy import AuthorizationPolicy
from infrastructure.adapters.input.api.dependencies import (
    require_manager_or_integration, require_organization_manager, require_organization_member,
)
from infrastructure.adapters.input.api.leads.mappers import paginate, to_detail_response, to_stats_response
from infrastructure.adapters.input.api.leads.schemas import (
    AssignLeadRequest, DiscardLeadRequest, LeadDetailResponse, LeadStatsResponse, PaginatedLeadsResponse,
)
from infrastructure.adapters.input.api.use_case_factories import (
    get_assign_lead_use_case, get_discard_lead_use_case, get_get_lead_stats_use_case,
    get_get_lead_use_case, get_get_leads_use_case, get_get_my_leads_use_case,
)

router = APIRouter()


@router.get("", response_model=PaginatedLeadsResponse, status_code=status.HTTP_200_OK)
@router.get("/", response_model=PaginatedLeadsResponse, status_code=status.HTTP_200_OK, include_in_schema=False)
def list_leads(
    status: Optional[str] = None,
    assigned_agent_id: Optional[UUID] = None,
    group_id: Optional[UUID] = None,
    source_id: Optional[UUID] = None,
    q: Optional[str] = None,
    # What changed since an instant, for a consumer catching up on what it
    # missed. Combined with status=UNASSIGNED it also answers "the ones nobody
    # is working", which is the other half of the same question.
    updated_since: Optional[datetime] = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    # Manager-only, and deliberately not "authenticated org member": this
    # endpoint returns the whole organization's pipeline, so a sales agent
    # reaching it would read its colleagues' leads. The agent's own view is
    # GET /leads/mine, a separate endpoint rather than a role branch in here.
    # A machine credential is the other door in (ADR-0028): identity
    # introspects the integration key and this service sees ptype=integration. It is
    # the only endpoint that opens for it, since a reobtaining integration is
    # the one use case the encargo asks for, not a second kind of human session.
    context: RequestContext = Depends(require_manager_or_integration),
    use_case: GetLeadsInputPort = Depends(get_get_leads_use_case),
) -> PaginatedLeadsResponse:
    query = GetLeadsQuery(
        tenant_id=context.tenant_id,
        status=status,
        assigned_agent_id=assigned_agent_id,
        group_id=group_id,
        source_id=source_id,
        search=q,
        updated_since=updated_since,
        limit=limit,
        offset=offset,
    )
    page = use_case.execute(query)
    return paginate(page.items, page.total, limit, offset)


# Declared before /{lead_id}: FastAPI resolves routes in declaration order, so
# "mine" would otherwise be swallowed by the parametric route and rejected as
# an invalid UUID.
@router.get("/mine", response_model=PaginatedLeadsResponse, status_code=status.HTTP_200_OK)
def list_my_leads(
    status: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    context: RequestContext = Depends(require_organization_member),
    use_case: GetMyLeadsInputPort = Depends(get_get_my_leads_use_case),
) -> PaginatedLeadsResponse:
    query = GetMyLeadsQuery(
        tenant_id=context.tenant_id,
        agent_id=context.principal.id,
        status=status,
        search=q,
        limit=limit,
        offset=offset,
    )
    page = use_case.execute(query)
    return paginate(page.items, page.total, limit, offset)


# Declared before /{lead_id}, same reason as /mine above: FastAPI resolves
# routes in declaration order, so "stats" would otherwise be swallowed by the
# parametric route and rejected as an invalid UUID.
@router.get("/stats", response_model=LeadStatsResponse, status_code=status.HTTP_200_OK)
def get_lead_stats(
    date_from: Optional[datetime] = Query(default=None, alias="from"),
    date_to: Optional[datetime] = Query(default=None, alias="to"),
    # Manager-only, no role branch: this is the whole organization's
    # snapshot, same as GET /leads. An agent's view is GET /leads/mine.
    context: RequestContext = Depends(require_organization_manager),
    use_case: GetLeadStatsInputPort = Depends(get_get_lead_stats_use_case),
) -> LeadStatsResponse:
    query = GetLeadStatsQuery(tenant_id=context.tenant_id, date_from=date_from, date_to=date_to)
    return to_stats_response(use_case.execute(query))


@router.get("/{lead_id}", response_model=LeadDetailResponse, status_code=status.HTTP_200_OK)
def get_lead(
    lead_id: UUID,
    context: RequestContext = Depends(require_organization_member),
    use_case: GetLeadInputPort = Depends(get_get_lead_use_case),
) -> LeadDetailResponse:
    lead = use_case.execute(GetLeadQuery(tenant_id=context.tenant_id, lead_id=lead_id))
    assigned_agent_id = lead.assigned_agent_id.value if lead.assigned_agent_id else None
    if not AuthorizationPolicy.can_view_lead(context.principal, lead.tenant_id.value, assigned_agent_id):
        # Same anti-enumeration rule as get_by_id_and_tenant: a colleague's
        # lead must read back as missing, not merely forbidden, or a 403
        # would confirm to the agent that the lead exists in their org.
        raise DomainException("El lead no existe", error_code="LEAD_NOT_FOUND")
    return to_detail_response(lead)


@router.post("/{lead_id}/assign", response_model=LeadDetailResponse, status_code=status.HTTP_200_OK)
def assign_lead(
    lead_id: UUID,
    request: AssignLeadRequest,
    context: RequestContext = Depends(require_organization_manager),
    use_case: AssignLeadInputPort = Depends(get_assign_lead_use_case),
) -> LeadDetailResponse:
    command = AssignLeadCommand(tenant_id=context.tenant_id, lead_id=lead_id, agent_id=request.agent_id)
    return to_detail_response(use_case.execute(command))


@router.post("/{lead_id}/discard", response_model=LeadDetailResponse, status_code=status.HTTP_200_OK)
def discard_lead(
    lead_id: UUID,
    request: DiscardLeadRequest,
    context: RequestContext = Depends(require_organization_manager),
    use_case: DiscardLeadInputPort = Depends(get_discard_lead_use_case),
) -> LeadDetailResponse:
    command = DiscardLeadCommand(tenant_id=context.tenant_id, lead_id=lead_id, reason=request.reason)
    return to_detail_response(use_case.execute(command))
