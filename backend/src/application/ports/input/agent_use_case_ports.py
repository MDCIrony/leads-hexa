from abc import ABC, abstractmethod
from typing import List
from application.dtos.queries import GetAgentsQuery, GetAgentQuery
from application.dtos.commands import CreateAgentCommand, AgentsPageResult
from domain.entities.agent import Agent

class GetAgentsInputPort(ABC):
    @abstractmethod
    def execute(self, query: GetAgentsQuery) -> AgentsPageResult:
        pass

class GetAgentInputPort(ABC):
    @abstractmethod
    def execute(self, query: GetAgentQuery) -> Agent:
        pass

class CreateAgentInputPort(ABC):
    @abstractmethod
    def execute(self, command: CreateAgentCommand) -> Agent:
        pass
