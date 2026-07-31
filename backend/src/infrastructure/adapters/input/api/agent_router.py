from uuid import UUID
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from domain.entities.agent import Agent
from domain.value_objects.agent_id import AgentId
from application.ports.output.agent_repository_port import AgentRepositoryPort
from infrastructure.adapters.input.api.dependencies import get_agent_repo
from infrastructure.adapters.input.api.schemas import AgentCreate, AgentResponse

router = APIRouter()

@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=AgentResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_agent(
    request: AgentCreate,
    agent_repo: AgentRepositoryPort = Depends(get_agent_repo),
):
    agent_id = AgentId()
    agent = Agent(
        id=agent_id,
        name=request.name,
        email=request.email,
        team=request.team,
        active_leads_count=request.active_leads_count,
        is_active=request.is_active,
    )
    saved = agent_repo.save(agent)
    return AgentResponse(
        id=str(saved.id),
        name=saved.name,
        email=saved.email,
        team=saved.team,
        active_leads_count=saved.active_leads_count,
        is_active=saved.is_active,
    )

@router.get("", response_model=List[AgentResponse], status_code=status.HTTP_200_OK)
@router.get("/", response_model=List[AgentResponse], status_code=status.HTTP_200_OK, include_in_schema=False)
def list_agents(
    team: Optional[str] = None,
    agent_repo: AgentRepositoryPort = Depends(get_agent_repo),
):
    agents = agent_repo.get_available_agents(team=team)
    return [
        AgentResponse(
            id=str(a.id),
            name=a.name,
            email=a.email,
            team=a.team,
            active_leads_count=a.active_leads_count,
            is_active=a.is_active,
        )
        for a in agents
    ]

@router.get("/{agent_id}", response_model=AgentResponse, status_code=status.HTTP_200_OK)
def get_agent(
    agent_id: UUID,
    agent_repo: AgentRepositoryPort = Depends(get_agent_repo),
):
    agent = agent_repo.get_by_id(agent_id)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return AgentResponse(
        id=str(agent.id),
        name=agent.name,
        email=agent.email,
        team=agent.team,
        active_leads_count=agent.active_leads_count,
        is_active=agent.is_active,
    )
