from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID
from domain.entities.agent import Agent

class AgentRepositoryPort(ABC):
    @abstractmethod
    def get_available_agents(self, tenant_id: UUID, team: Optional[str] = None) -> List[Agent]:
        """Return the active agents of this organization eligible for assignment.

        tenant_id is required and comes first: an optional organization filter
        is one forgotten argument away from routing a lead into someone else's
        company."""

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

    # list_by_tenant is a prerequisite pulled in from Task 5 (organization
    # filtering): Task 4's UpdateTenantUseCase needs it to deactivate an
    # organization's agents when the organization itself is deactivated.
    @abstractmethod
    def list_by_tenant(
        self,
        tenant_id: UUID,
        team: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Agent]:
        """Return a page of active agents of this organization."""

    @abstractmethod
    def count_by_tenant(self, tenant_id: UUID, team: Optional[str] = None) -> int:
        """Return how many active agents this organization has."""

    @abstractmethod
    def get_by_id_and_tenant(self, agent_id: UUID, tenant_id: UUID) -> Optional[Agent]:
        """Return the agent only when it belongs to this organization.

        Returning None for an agent of another organization is deliberate: a
        403 would confirm that the identifier exists."""

    @abstractmethod
    def deactivate_all_by_tenant(self, tenant_id: UUID) -> int:
        """Deactivate every active agent of this organization, returning how many.

        A single statement rather than a paged loop: suspending an organization
        must leave no working credential behind, and any page size is a silent
        ceiling on that guarantee."""

    @abstractmethod
    def distinct_tenant_ids(self) -> List[UUID]:
        """Return every organization identifier referenced by an agent.

        Used by the backfill command of Task 7; declared here so the port is
        modified once instead of twice."""
