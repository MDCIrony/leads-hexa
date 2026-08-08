from application.dtos.queries import GetAgentsQuery, GetAgentQuery
from application.dtos.commands import AgentsPageResult, CreateAgentCommand, UpdateAgentCommand
from application.ports.input.agent_use_case_ports import (
    CreateAgentInputPort,
    DeactivateAgentInputPort,
    GetAgentInputPort,
    GetAgentsInputPort,
    UpdateAgentInputPort,
)
from application.ports.output.password_hasher_port import PasswordHasherPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from domain.entities.agent import Agent
from domain.exceptions import AgentNotFoundException, DomainException
from domain.value_objects.group_id import GroupId

class GetAgentsUseCase(GetAgentsInputPort):
    def __init__(self, uow: UnitOfWorkPort):
        self.uow = uow

    def execute(self, query: GetAgentsQuery) -> AgentsPageResult:
        with self.uow:
            items = self.uow.agents.list_by_tenant(
                query.tenant_id, group_id=query.group_id, limit=query.limit, offset=query.offset
            )
            total = self.uow.agents.count_by_tenant(query.tenant_id, group_id=query.group_id)
        return AgentsPageResult(items=items, total=total)

class GetAgentUseCase(GetAgentInputPort):
    def __init__(self, uow: UnitOfWorkPort):
        self.uow = uow

    def execute(self, query: GetAgentQuery) -> Agent:
        with self.uow:
            agent = self.uow.agents.get_by_id_and_tenant(query.agent_id, query.tenant_id)
        if agent is None:
            raise AgentNotFoundException()
        return agent

class CreateAgentUseCase(CreateAgentInputPort):
    def __init__(self, uow: UnitOfWorkPort, password_hasher: PasswordHasherPort):
        self.uow = uow
        self.password_hasher = password_hasher

    def execute(self, command: CreateAgentCommand) -> Agent:
        agent = Agent.create(
            name=command.name,
            email=command.email,
            group_id=command.group_id,
            is_active=command.is_active,
            role=command.role,
            hashed_password=self.password_hasher.hash(command.password),
            tenant_id=command.tenant_id,
        )
        with self.uow:
            return self.uow.agents.save(agent)


def _get_owned_agent(uow: UnitOfWorkPort, tenant_id, agent_id) -> Agent:
    """Scoped through get_by_id_and_tenant so an agent belonging to another
    organization reads back as missing rather than confirming it exists."""
    agent = uow.agents.get_by_id_and_tenant(agent_id, tenant_id)
    if agent is None:
        raise AgentNotFoundException()
    return agent


class UpdateAgentUseCase(UpdateAgentInputPort):
    def __init__(self, uow: UnitOfWorkPort):
        self.uow = uow

    def execute(self, command: UpdateAgentCommand) -> Agent:
        with self.uow:
            agent = _get_owned_agent(self.uow, command.tenant_id, command.agent_id)
            if command.name is not None:
                agent.name = command.name
            if command.group_id is not None:
                group = self.uow.groups.get_by_id(command.group_id)
                if group is None or str(group.tenant_id) != str(command.tenant_id):
                    raise DomainException(
                        "El grupo no existe", error_code="GROUP_NOT_FOUND"
                    )
                agent.group_id = GroupId(command.group_id)
            return self.uow.agents.save(agent)


class DeactivateAgentUseCase(DeactivateAgentInputPort):
    def __init__(self, uow: UnitOfWorkPort):
        self.uow = uow

    def execute(self, query: GetAgentQuery) -> Agent:
        with self.uow:
            agent = _get_owned_agent(self.uow, query.tenant_id, query.agent_id)
            # Deactivate, never delete: leads already assigned to this agent
            # keep pointing at it, and get_available_agents already filters
            # on is_active, so it simply stops receiving new ones.
            agent.is_active = False
            return self.uow.agents.save(agent)
