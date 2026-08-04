from typing import List
from application.dtos.queries import GetAgentsQuery, GetAgentQuery
from application.dtos.commands import CreateAgentCommand, AgentsPageResult
from application.ports.input.agent_use_case_ports import (
    GetAgentsInputPort, GetAgentInputPort, CreateAgentInputPort
)
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from domain.entities.agent import Agent
from domain.exceptions import AgentNotFoundException
from infrastructure.security.password_hasher import hash_password

class GetAgentsUseCase(GetAgentsInputPort):
    def __init__(self, uow: UnitOfWorkPort):
        self.uow = uow

    def execute(self, query: GetAgentsQuery) -> AgentsPageResult:
        with self.uow:
            items = self.uow.agents.list_active(team=query.team, limit=query.limit, offset=query.offset)
            total = self.uow.agents.count_active(team=query.team)
        return AgentsPageResult(items=items, total=total)

class GetAgentUseCase(GetAgentInputPort):
    def __init__(self, uow: UnitOfWorkPort):
        self.uow = uow

    def execute(self, query: GetAgentQuery) -> Agent:
        with self.uow:
            agent = self.uow.agents.get_by_id(query.agent_id)
        if agent is None:
            raise AgentNotFoundException()
        return agent

class CreateAgentUseCase(CreateAgentInputPort):
    def __init__(self, uow: UnitOfWorkPort):
        self.uow = uow

    def execute(self, command: CreateAgentCommand) -> Agent:
        agent = Agent.create(
            name=command.name,
            email=command.email,
            team=command.team,
            active_leads_count=command.active_leads_count,
            is_active=command.is_active,
            role=command.role,
            hashed_password=hash_password(command.password),
            tenant_id=command.tenant_id,
        )
        with self.uow:
            return self.uow.agents.save(agent)

