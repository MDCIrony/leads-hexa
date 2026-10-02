from abc import ABC, abstractmethod
from uuid import UUID

from domain.agents.agent import Agent


class AgentRepositoryPort(ABC):
    @abstractmethod
    def save(self, agent: Agent) -> Agent:
        """Insert or update; returns the agent with the version the database assigned."""

    @abstractmethod
    def get_by_id(self, agent_id: UUID) -> Agent | None: ...

    @abstractmethod
    def get_by_email(self, email: str) -> Agent | None:
        """Looks up an already normalized email."""

    @abstractmethod
    def count(self) -> int:
        """Every agent, any organization: zero means the platform is not bootstrapped yet."""

    @abstractmethod
    def list_by_tenant(
        self, tenant_id: UUID, is_active: bool | None = True, limit: int = 100, offset: int = 0
    ) -> list[Agent]:
        """A page of this organization's agents. is_active=None lists both states."""

    @abstractmethod
    def count_by_tenant(self, tenant_id: UUID, is_active: bool | None = True) -> int:
        """Same filter as list_by_tenant, or total counts a different population than items."""

    @abstractmethod
    def get_by_id_and_tenant(self, agent_id: UUID, tenant_id: UUID) -> Agent | None:
        """None for an agent of another organization: a 403 would confirm it exists."""

    @abstractmethod
    def deactivate_all_by_tenant(self, tenant_id: UUID) -> list[Agent]:
        """Deactivate every active agent of the organization in one statement, returning
        them with their new version. Any page size would be a silent ceiling on a
        suspension that must leave no working credential behind."""

    @abstractmethod
    def distinct_tenant_ids(self) -> list[UUID]:
        """Every organization an agent points at; for the sync_tenants CLI."""

    @abstractmethod
    def list_all(self, limit: int = 100, offset: int = 0) -> list[Agent]:
        """Every agent, any organization, state or role; for the identity snapshot,
        which must also carry the platform admin and the machine credentials."""
