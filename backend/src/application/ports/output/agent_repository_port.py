from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID
from domain.entities.agent import Agent

class AgentRepositoryPort(ABC):
    @abstractmethod
    def get_available_agents(self, team: Optional[str] = None) -> List[Agent]:
        pass

    @abstractmethod
    def update_active_count(self, agent_id: UUID, new_count: int) -> None:
        pass

    @abstractmethod
    def save(self, agent: Agent) -> Agent:
        pass

    @abstractmethod
    def get_by_id(self, agent_id: UUID) -> Optional[Agent]:
        pass

    @abstractmethod
    def list_active(self, team: Optional[str] = None, limit: int = 100, offset: int = 0) -> List[Agent]:
        pass

    @abstractmethod
    def count_active(self, team: Optional[str] = None) -> int:
        pass

    @abstractmethod
    def get_by_email(self, email: str) -> Optional[Agent]:
        pass

    @abstractmethod
    def count(self) -> int:
        pass
