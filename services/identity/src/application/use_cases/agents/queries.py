from uuid import UUID

from application.dtos.agents import AgentsPageResult, GetAgentQuery, GetAgentsQuery
from application.ports.input.agents import GetAgentInputPort, GetAgentsInputPort, GetAgentStateInputPort
from application.ports.output.unit_of_work import UnitOfWorkPort
from domain.agents.agent import Agent
from domain.events.identity_events import AgentState
from domain.exceptions import AgentNotFoundException


class GetAgentsUseCase(GetAgentsInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, query: GetAgentsQuery) -> AgentsPageResult:
        with self.uow:
            items = self.uow.agents.list_by_tenant(
                query.tenant_id, is_active=query.is_active, limit=query.limit, offset=query.offset
            )
            total = self.uow.agents.count_by_tenant(query.tenant_id, is_active=query.is_active)
        return AgentsPageResult(items=items, total=total)


class GetAgentUseCase(GetAgentInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, query: GetAgentQuery) -> Agent:
        with self.uow:
            agent = self.uow.agents.get_by_id_and_tenant(query.agent_id, query.tenant_id)
        if agent is None:
            raise AgentNotFoundException()
        return agent


class GetAgentStateUseCase(GetAgentStateInputPort):
    """The same snapshot the AgentState event carries, for a service that missed it."""

    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, agent_id: UUID) -> AgentState:
        with self.uow:
            agent = self.uow.agents.get_by_id(agent_id)
        if agent is None:
            raise AgentNotFoundException()
        return AgentState.of(agent)
