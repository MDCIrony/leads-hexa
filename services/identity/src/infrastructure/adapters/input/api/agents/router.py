from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from application.dtos.agents import (
    CreateAgentCommand, GetAgentQuery, GetAgentsQuery, IssueIntegrationCredentialCommand, UpdateAgentCommand,
)
from application.dtos.context import Principal, RequestContext
from application.ports.input.agents import (
    CreateAgentInputPort, DeactivateAgentInputPort, GetAgentInputPort, GetAgentsInputPort,
    IssueIntegrationCredentialInputPort, UpdateAgentInputPort,
)
from application.ports.output.unit_of_work import UnitOfWorkPort
from domain.exceptions import UnauthorizedException
from domain.policies.authorization_policy import AuthorizationPolicy
from domain.value_objects.agent_role import AgentRole
from infrastructure.adapters.input.api.agents.schemas import (
    AgentCreate, AgentResponse, AgentUpdate, IntegrationCredentialResponse, PaginatedAgentsResponse,
    to_agent_response,
)
from infrastructure.adapters.input.api.dependencies import (
    build_request_context, get_container, get_optional_human_principal, get_uow, require_organization_manager,
)
from infrastructure.adapters.input.api.use_case_factories import (
    get_create_agent_use_case, get_deactivate_agent_use_case, get_get_agent_use_case, get_get_agents_use_case,
    get_issue_integration_credential_use_case, get_update_agent_use_case,
)
from infrastructure.di.container import Container

router = APIRouter()


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=AgentResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_agent(
    request: AgentCreate,
    use_case: CreateAgentInputPort = Depends(get_create_agent_use_case),
    uow: UnitOfWorkPort = Depends(get_uow),
    principal: Optional[Principal] = Depends(get_optional_human_principal),
):
    with uow:
        is_bootstrap = uow.agents.count() == 0

    # On an empty platform the first, anonymous caller becomes its administrator,
    # whatever role the body asks for: the only way into the platform plane.
    if is_bootstrap:
        role, tenant_id = AgentRole.ADMIN, None
    else:
        if principal is None:
            raise UnauthorizedException("Authentication required to create an agent")
        AuthorizationPolicy.ensure_can_create_agent_with_role(principal, request.role)
        role, tenant_id = request.role, build_request_context(principal).tenant_id

    command = CreateAgentCommand(
        name=request.name, email=request.email, password=request.password,
        is_active=request.is_active, role=role.value, tenant_id=tenant_id,
    )
    return to_agent_response(use_case.execute(command))


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


@router.get("", response_model=PaginatedAgentsResponse)
@router.get("/", response_model=PaginatedAgentsResponse, include_in_schema=False)
def list_agents(
    # True when absent: only active agents. ?is_active=false is the trash view for reactivation.
    is_active: Optional[bool] = True,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    use_case: GetAgentsInputPort = Depends(get_get_agents_use_case),
    context: RequestContext = Depends(require_organization_manager),
):
    page = use_case.execute(
        GetAgentsQuery(tenant_id=context.tenant_id, is_active=is_active, limit=limit, offset=offset)
    )
    items = [to_agent_response(agent) for agent in page.items]
    return PaginatedAgentsResponse(
        items=items, total=page.total, limit=limit, offset=offset, has_more=(offset + len(items)) < page.total,
    )


@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent(
    agent_id: UUID,
    use_case: GetAgentInputPort = Depends(get_get_agent_use_case),
    context: RequestContext = Depends(require_organization_manager),
):
    return to_agent_response(use_case.execute(GetAgentQuery(agent_id=agent_id, tenant_id=context.tenant_id)))


@router.patch("/{agent_id}", response_model=AgentResponse)
def update_agent(
    agent_id: UUID,
    request: AgentUpdate,
    use_case: UpdateAgentInputPort = Depends(get_update_agent_use_case),
    context: RequestContext = Depends(require_organization_manager),
):
    command = UpdateAgentCommand(
        tenant_id=context.tenant_id, agent_id=agent_id, name=request.name, is_active=request.is_active,
    )
    return to_agent_response(use_case.execute(command))


@router.delete("/{agent_id}", response_model=AgentResponse)
def deactivate_agent(
    agent_id: UUID,
    use_case: DeactivateAgentInputPort = Depends(get_deactivate_agent_use_case),
    context: RequestContext = Depends(require_organization_manager),
):
    # Deactivates rather than deletes: leads already assigned keep a valid reference.
    return to_agent_response(use_case.execute(GetAgentQuery(agent_id=agent_id, tenant_id=context.tenant_id)))
