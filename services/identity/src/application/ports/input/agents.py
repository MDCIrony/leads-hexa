from abc import ABC, abstractmethod
from uuid import UUID

from application.dtos.agents import (
    AgentsPageResult,
    CreateAgentCommand,
    GetAgentQuery,
    GetAgentsQuery,
    IntegrationCredentialResult,
    IssueIntegrationCredentialCommand,
    UpdateAgentCommand,
)
from domain.agents.agent import Agent
from domain.events.identity_events import AgentState


class GetAgentsInputPort(ABC):
    @abstractmethod
    def execute(self, query: GetAgentsQuery) -> AgentsPageResult: ...


class GetAgentInputPort(ABC):
    @abstractmethod
    def execute(self, query: GetAgentQuery) -> Agent: ...


class CreateAgentInputPort(ABC):
    @abstractmethod
    def execute(self, command: CreateAgentCommand) -> Agent: ...


class UpdateAgentInputPort(ABC):
    @abstractmethod
    def execute(self, command: UpdateAgentCommand) -> Agent: ...


class DeactivateAgentInputPort(ABC):
    @abstractmethod
    def execute(self, query: GetAgentQuery) -> Agent: ...


class IssueIntegrationCredentialInputPort(ABC):
    @abstractmethod
    def execute(self, command: IssueIntegrationCredentialCommand) -> IntegrationCredentialResult: ...


class GetAgentStateInputPort(ABC):
    @abstractmethod
    def execute(self, agent_id: UUID) -> AgentState:
        """Any organization, any state: for trusted services only. AgentNotFoundException if absent."""
