from typing import Protocol

from domain.exceptions import ForbiddenException
from domain.value_objects.agent_role import AgentRole


class Actor(Protocol):
    """Anything that acts: an application-level Principal."""

    role: AgentRole


class AuthorizationPolicy:
    """Who may manage an organization's sources and intake.

    The platform administrator has no organization, so it manages none: a
    compromised platform credential stays away from every customer's data."""

    @staticmethod
    def can_manage_organization(actor: Actor) -> bool:
        return actor.role == AgentRole.MANAGER

    @staticmethod
    def ensure_can_manage_organization(actor: Actor) -> None:
        if not AuthorizationPolicy.can_manage_organization(actor):
            raise ForbiddenException(
                f"Role {actor.role.value} is not permitted to manage an organization"
            )
