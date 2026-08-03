from typing import List
from application.dtos.queries import GetAgentsQuery, GetAgentQuery
from application.dtos.commands import CreateAgentCommand
from application.ports.input.agent_use_case_ports import (
    GetAgentsInputPort, GetAgentInputPort, CreateAgentInputPort
)
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from domain.entities.agent import Agent

class GetAgentsUseCase(GetAgentsInputPort):
    def __init__(self, uow: UnitOfWorkPort):
        self.uow = uow

    def execute(self, query: GetAgentsQuery) -> List[Agent]:
        with self.uow:
            return self.uow.agents.get_available_agents(team=query.team)

class GetAgentUseCase(GetAgentInputPort):
    def __init__(self, uow: UnitOfWorkPort):
        self.uow = uow

    def execute(self, query: GetAgentQuery) -> Agent:
        with self.uow:
            return self.uow.agents.get_by_id(query.agent_id)

class CreateAgentUseCase(CreateAgentInputPort):
    def __init__(self, uow: UnitOfWorkPort):
        self.uow = uow

    def execute(self, command: CreateAgentCommand) -> Agent:
        agent = Agent.create(
            name=command.name,
            email=command.email,
            team=command.team,
            active_leads_count=command.active_leads_count,
            is_active=command.is_active
        )
        with self.uow:
            return self.uow.agents.save(agent)
