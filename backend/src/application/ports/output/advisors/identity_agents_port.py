from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from domain.advisors.advisor import Advisor


class IdentityAgentsPort(ABC):
    """identity, the owner of agents, asked for one it may not have announced yet."""

    @abstractmethod
    def fetch(self, agent_id: UUID) -> Optional[Advisor]:
        """The agent as identity holds it now, or None if it has none or the agent has no organization.

        Raises SERVICE_UNAVAILABLE when identity cannot answer: "unknown" and
        "unreachable" must never be confused, or an outage reads as a 404."""
