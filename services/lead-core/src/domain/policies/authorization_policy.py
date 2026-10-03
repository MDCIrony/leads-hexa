from typing import Optional, Protocol
from uuid import UUID

from domain.exceptions import ForbiddenException
from domain.value_objects.enums import AgentRole


class Actor(Protocol):
    """Anything that acts: an application-level Principal."""

    id: object
    tenant_id: object
    role: AgentRole


def _same_id(left, right) -> bool:
    """Identifiers arrive as value objects, UUIDs or strings depending on the
    caller, so they are compared by their textual form."""
    return left is not None and right is not None and str(left) == str(right)


class AuthorizationPolicy:
    """Single source of truth for who may do what on an organization's data.

    The platform administrator is not a more powerful manager: it has no
    organization, so it reaches none. That keeps a compromised platform
    credential away from every customer's data."""

    # --- Organization plane -------------------------------------------------

    @staticmethod
    def can_access_tenant(actor: Actor, tenant_id: UUID) -> bool:
        # The platform administrator has no organization and reaches none.
        return _same_id(actor.tenant_id, tenant_id)

    @staticmethod
    def ensure_can_access_tenant(actor: Actor, tenant_id: UUID) -> None:
        if not AuthorizationPolicy.can_access_tenant(actor, tenant_id):
            raise ForbiddenException("You do not have access to this organization's data")

    @staticmethod
    def can_manage_organization(actor: Actor) -> bool:
        return actor.role == AgentRole.MANAGER

    @staticmethod
    def ensure_can_manage_organization(actor: Actor) -> None:
        if not AuthorizationPolicy.can_manage_organization(actor):
            raise ForbiddenException(
                f"Role {actor.role.value} is not permitted to manage an organization"
            )

    @staticmethod
    def can_view_lead(
        actor: Actor,
        lead_tenant_id: UUID,
        lead_assigned_agent_id: Optional[UUID],
    ) -> bool:
        if not AuthorizationPolicy.can_access_tenant(actor, lead_tenant_id):
            return False
        if AuthorizationPolicy.can_manage_organization(actor):
            return True
        # A sales agent sees only what is assigned to them.
        return _same_id(actor.id, lead_assigned_agent_id)

    @staticmethod
    def ensure_can_view_lead(
        actor: Actor,
        lead_tenant_id: UUID,
        lead_assigned_agent_id: Optional[UUID],
    ) -> None:
        if not AuthorizationPolicy.can_view_lead(actor, lead_tenant_id, lead_assigned_agent_id):
            raise ForbiddenException("You do not have access to this lead")
