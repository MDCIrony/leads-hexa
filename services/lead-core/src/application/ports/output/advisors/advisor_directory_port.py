from abc import ABC, abstractmethod
from uuid import UUID

from domain.advisors.advisor import Advisor


class AdvisorDirectoryPort(ABC):
    @abstractmethod
    def get(self, agent_id: UUID, tenant_id: UUID) -> Advisor:
        """An advisor of this organization that work can be routed to, hydrated
        from identity when the projection has not seen it yet.

        Raises AGENT_NOT_FOUND for an unknown agent, one of another organization
        or one that is never routed work; SERVICE_UNAVAILABLE if identity is down."""
