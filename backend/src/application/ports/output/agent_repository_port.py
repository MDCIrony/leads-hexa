from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID
from domain.entities.agent import Agent

class AgentRepositoryPort(ABC):
    @abstractmethod
    def get_available_agents(self, tenant_id: UUID, group_id: Optional[UUID] = None) -> List[Agent]:
        """Return the active agents of this organization eligible for assignment.

        tenant_id is required and comes first: an optional organization filter
        is one forgotten argument away from routing a lead into someone else's
        company."""

    @abstractmethod
    def save(self, agent: Agent) -> Agent:
        pass

    @abstractmethod
    def get_by_id(self, agent_id: UUID) -> Optional[Agent]:
        pass

    @abstractmethod
    def list_active(self, group_id: Optional[UUID] = None, limit: int = 100, offset: int = 0) -> List[Agent]:
        pass

    @abstractmethod
    def count_active(self, group_id: Optional[UUID] = None) -> int:
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
        group_id: Optional[UUID] = None,
        is_active: Optional[bool] = True,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Agent]:
        """Return a page of this organization's agents.

        is_active defaults to True so every caller written before this
        filter existed keeps seeing only active agents; pass False for the
        deactivated ones, or None for both."""

    @abstractmethod
    def count_by_tenant(
        self, tenant_id: UUID, group_id: Optional[UUID] = None, is_active: Optional[bool] = True
    ) -> int:
        """Return how many agents match, honoring the same is_active filter as list_by_tenant."""

    @abstractmethod
    def get_by_id_and_tenant(self, agent_id: UUID, tenant_id: UUID) -> Optional[Agent]:
        """Return the agent only when it belongs to this organization.

        Returning None for an agent of another organization is deliberate: a
        403 would confirm that the identifier exists."""

    @abstractmethod
    def deactivate_all_by_tenant(self, tenant_id: UUID) -> List[Agent]:
        """Deactivate every active agent of this organization, returning them
        as they are now, new version included: each one is a write that
        downstream copies of the agent must hear about.

        A single statement rather than a paged loop: suspending an organization
        must leave no working credential behind, and any page size is a silent
        ceiling on that guarantee."""

    @abstractmethod
    def distinct_tenant_ids(self) -> List[UUID]:
        """Return every organization identifier referenced by an agent.

        Used by the backfill command of Task 7; declared here so the port is
        modified once instead of twice."""
