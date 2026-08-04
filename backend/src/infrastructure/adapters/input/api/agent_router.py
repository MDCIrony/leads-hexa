from uuid import UUID
from typing import List, Optional
from fastapi import APIRouter, Depends, status
from application.dtos.commands import CreateAgentCommand
from application.dtos.queries import GetAgentsQuery, GetAgentQuery
from application.ports.input.agent_use_case_ports import (
    CreateAgentInputPort, GetAgentsInputPort, GetAgentInputPort
)
from infrastructure.adapters.input.api.dependencies import (
    get_create_agent_use_case, get_get_agents_use_case, get_get_agent_use_case
)
from infrastructure.adapters.input.api.schemas import AgentCreate, AgentResponse, PaginatedAgentsResponse

router = APIRouter()

@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=AgentResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_agent(
    request: AgentCreate,
    use_case: CreateAgentInputPort = Depends(get_create_agent_use_case),
):
    command = CreateAgentCommand(
        name=request.name,
        email=request.email,
        team=request.team,
        active_leads_count=request.active_leads_count,
        is_active=request.is_active,
    )
    saved = use_case.execute(command)
    return AgentResponse(
        id=str(saved.id),
        name=saved.name,
        email=saved.email,
        team=saved.team,
        active_leads_count=saved.active_leads_count,
        is_active=saved.is_active,
    )

@router.get("", response_model=PaginatedAgentsResponse, status_code=status.HTTP_200_OK)
@router.get("/", response_model=PaginatedAgentsResponse, status_code=status.HTTP_200_OK, include_in_schema=False)
def list_agents(
    team: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    use_case: GetAgentsInputPort = Depends(get_get_agents_use_case),
):
    query = GetAgentsQuery(team=team, limit=limit, offset=offset)
    page = use_case.execute(query)
    items = [
        AgentResponse(
            id=str(a.id),
            name=a.name,
            email=a.email,
            team=a.team,
            active_leads_count=a.active_leads_count,
            is_active=a.is_active,
        )
        for a in page.items
    ]
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
):
    query = GetAgentQuery(agent_id=agent_id)
    agent = use_case.execute(query)
    return AgentResponse(
        id=str(agent.id),
        name=agent.name,
        email=agent.email,
        team=agent.team,
        active_leads_count=agent.active_leads_count,
        is_active=agent.is_active,
    )
