from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, status

from application.dtos.commands import CreateAgentCommand
from application.dtos.context import RequestContext
from application.dtos.queries import GetAgentsQuery, GetAgentQuery
from application.ports.input.agent_use_case_ports import (
    CreateAgentInputPort, GetAgentsInputPort, GetAgentInputPort
)
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from domain.entities.agent import Agent
from domain.exceptions import UnauthorizedException
from domain.policies.authorization_policy import AuthorizationPolicy
from domain.value_objects.enums import AgentRole
from infrastructure.adapters.input.api.dependencies import (
    get_create_agent_use_case, get_get_agents_use_case, get_get_agent_use_case,
    build_request_context, get_optional_current_agent, get_uow, require_organization_manager,
)
from infrastructure.adapters.input.api.schemas import AgentCreate, AgentResponse, PaginatedAgentsResponse

router = APIRouter()


def _to_response(agent: Agent) -> AgentResponse:
    return AgentResponse(
        id=str(agent.id),
        name=agent.name,
        email=agent.email,
        team=agent.team,
        active_leads_count=agent.active_leads_count,
        is_active=agent.is_active,
        role=agent.role.value if hasattr(agent.role, "value") else str(agent.role),
        tenant_id=str(agent.tenant_id) if agent.tenant_id else None,
    )


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=AgentResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_agent(
    request: AgentCreate,
    use_case: CreateAgentInputPort = Depends(get_create_agent_use_case),
    uow: UnitOfWorkPort = Depends(get_uow),
    current_agent: Optional[Agent] = Depends(get_optional_current_agent),
):
    with uow:
        is_bootstrap = uow.agents.count() == 0

    if is_bootstrap:
        forced_role = AgentRole.ADMIN
        tenant_id = None
    else:
        if current_agent is None:
            raise UnauthorizedException("Authentication required to create an agent")
        AuthorizationPolicy.ensure_can_create_agent_with_role(current_agent, request.role)
        # The organization is always the caller's own: there is no tenant_id
        # left in the request for a Manager to target another one with.
        tenant_id = build_request_context(current_agent).tenant_id
        forced_role = request.role

    command = CreateAgentCommand(
        name=request.name,
        email=request.email,
        team=request.team,
        active_leads_count=request.active_leads_count,
        is_active=request.is_active,
        password=request.password,
        role=forced_role.value if hasattr(forced_role, "value") else str(forced_role),
        tenant_id=tenant_id,
    )
    return _to_response(use_case.execute(command))


@router.get("", response_model=PaginatedAgentsResponse, status_code=status.HTTP_200_OK)
@router.get("/", response_model=PaginatedAgentsResponse, status_code=status.HTTP_200_OK, include_in_schema=False)
def list_agents(
    team: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    use_case: GetAgentsInputPort = Depends(get_get_agents_use_case),
    context: RequestContext = Depends(require_organization_manager),
):
    query = GetAgentsQuery(tenant_id=context.tenant_id, team=team, limit=limit, offset=offset)
    page = use_case.execute(query)
    items = [_to_response(a) for a in page.items]
    return PaginatedAgentsResponse(
        items=items,
        total=page.total,
        limit=limit,
        offset=offset,
        has_more=(offset + len(items)) < page.total,
    )


@router.get("/{agent_id}", response_model=AgentResponse, status_code=status.HTTP_200_OK)
def get_agent(
    agent_id: UUID,
    use_case: GetAgentInputPort = Depends(get_get_agent_use_case),
    context: RequestContext = Depends(require_organization_manager),
):
    query = GetAgentQuery(agent_id=agent_id, tenant_id=context.tenant_id)
    agent = use_case.execute(query)
    return _to_response(agent)

