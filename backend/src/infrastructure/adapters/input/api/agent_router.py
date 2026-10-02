from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, Query, status

from application.dtos.commands import CreateAgentCommand, IssueIntegrationCredentialCommand, UpdateAgentCommand
from application.dtos.context import RequestContext
from application.dtos.queries import GetAgentsQuery, GetAgentQuery
from application.ports.input.agent_use_case_ports import (
    CreateAgentInputPort, DeactivateAgentInputPort, GetAgentsInputPort, GetAgentInputPort,
    IssueIntegrationCredentialInputPort, UpdateAgentInputPort,
)
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from domain.entities.agent import Agent
from domain.exceptions import UnauthorizedException
from domain.policies.authorization_policy import AuthorizationPolicy
from domain.value_objects.enums import AgentRole
from infrastructure.adapters.input.api.dependencies import (
    get_container, get_create_agent_use_case, get_deactivate_agent_use_case, get_get_agents_use_case,
    get_get_agent_use_case, get_issue_integration_credential_use_case, get_update_agent_use_case,
    build_request_context, get_optional_current_agent, get_uow, principal_from_agent,
    require_organization_manager,
)
from infrastructure.adapters.input.api.schemas import (
    AgentCreate, AgentResponse, AgentUpdate, IntegrationCredentialResponse, PaginatedAgentsResponse,
)
from infrastructure.di.container import Container

router = APIRouter()


def _to_response(agent: Agent) -> AgentResponse:
    return AgentResponse(
        id=str(agent.id),
        name=agent.name,
        email=agent.email,
        group_id=str(agent.group_id) if agent.group_id else None,
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
        principal = principal_from_agent(current_agent)
        AuthorizationPolicy.ensure_can_create_agent_with_role(principal, request.role)
        # The organization is always the caller's own: there is no tenant_id
        # left in the request for a Manager to target another one with.
        tenant_id = build_request_context(principal).tenant_id
        forced_role = request.role

    command = CreateAgentCommand(
        name=request.name,
        email=request.email,
        group_id=request.group_id,
        is_active=request.is_active,
        password=request.password,
        role=forced_role.value if hasattr(forced_role, "value") else str(forced_role),
        tenant_id=tenant_id,
    )
    return _to_response(use_case.execute(command))


@router.post(
    "/integration-credential", response_model=IntegrationCredentialResponse, status_code=status.HTTP_201_CREATED
)
def issue_integration_credential(
    context: RequestContext = Depends(require_organization_manager),
    use_case: IssueIntegrationCredentialInputPort = Depends(get_issue_integration_credential_use_case),
    container: Container = Depends(get_container),
):
    result = use_case.execute(IssueIntegrationCredentialCommand(tenant_id=context.tenant_id))
    return IntegrationCredentialResponse(
        agent_id=str(result.agent.id),
        tenant_id=str(context.tenant_id),
        api_key=result.api_key,
        kafka_username=result.kafka_username,
        kafka_password=result.kafka_password,
        kafka_bootstrap_servers=container.settings.kafka_external_bootstrap_servers,
        kafka_topic=result.kafka_topic,
    )


@router.get("", response_model=PaginatedAgentsResponse, status_code=status.HTTP_200_OK)
@router.get("/", response_model=PaginatedAgentsResponse, status_code=status.HTTP_200_OK, include_in_schema=False)
def list_agents(
    group_id: Optional[UUID] = None,
    # True keeps today's behavior when the client sends nothing: only
    # active agents. ?is_active=false is the trash view for reactivation.
    is_active: Optional[bool] = True,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    use_case: GetAgentsInputPort = Depends(get_get_agents_use_case),
    context: RequestContext = Depends(require_organization_manager),
):
    query = GetAgentsQuery(
        tenant_id=context.tenant_id, group_id=group_id, is_active=is_active, limit=limit, offset=offset
    )
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


@router.patch("/{agent_id}", response_model=AgentResponse, status_code=status.HTTP_200_OK)
def update_agent(
    agent_id: UUID,
    request: AgentUpdate,
    use_case: UpdateAgentInputPort = Depends(get_update_agent_use_case),
    context: RequestContext = Depends(require_organization_manager),
):
    command = UpdateAgentCommand(
        tenant_id=context.tenant_id,
        agent_id=agent_id,
        name=request.name,
        group_id=request.group_id,
        is_active=request.is_active,
    )
    return _to_response(use_case.execute(command))


@router.delete("/{agent_id}", response_model=AgentResponse, status_code=status.HTTP_200_OK)
def deactivate_agent(
    agent_id: UUID,
    use_case: DeactivateAgentInputPort = Depends(get_deactivate_agent_use_case),
    context: RequestContext = Depends(require_organization_manager),
):
    # Deactivates rather than deletes: leads already assigned to this agent
    # keep a valid reference, so the row must survive.
    query = GetAgentQuery(agent_id=agent_id, tenant_id=context.tenant_id)
    return _to_response(use_case.execute(query))
