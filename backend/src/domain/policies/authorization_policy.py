from typing import Optional
from uuid import UUID

from domain.entities.agent import Agent
from domain.exceptions import ForbiddenException
from domain.value_objects.enums import AgentRole


def _same_id(left, right) -> bool:
    """Identifiers arrive as value objects, UUIDs or strings depending on the
    caller, so they are compared by their textual form."""
    return left is not None and right is not None and str(left) == str(right)


class AuthorizationPolicy:
    """Single source of truth for who may do what.

    The platform plane and the organization plane are disjoint: the
    administrator is not a more powerful manager, it operates on a different
    kind of object. That keeps a compromised platform credential away from
    every customer's data."""

    # --- Platform plane -----------------------------------------------------

    @staticmethod
    def can_manage_platform(actor: Agent) -> bool:
        return actor.role == AgentRole.ADMIN

    @staticmethod
    def ensure_can_manage_platform(actor: Agent) -> None:
        if not AuthorizationPolicy.can_manage_platform(actor):
            raise ForbiddenException("Only the platform administrator may perform this action")

    # --- Organization plane -------------------------------------------------

    @staticmethod
    def can_access_tenant(actor: Agent, tenant_id: UUID) -> bool:
        # The platform administrator has no organization and reaches none.
        return _same_id(actor.tenant_id, tenant_id)

    @staticmethod
    def ensure_can_access_tenant(actor: Agent, tenant_id: UUID) -> None:
        if not AuthorizationPolicy.can_access_tenant(actor, tenant_id):
            raise ForbiddenException("You do not have access to this organization's data")

    @staticmethod
    def can_manage_organization(actor: Agent) -> bool:
        return actor.role == AgentRole.MANAGER

    @staticmethod
    def ensure_can_manage_organization(actor: Agent) -> None:
        if not AuthorizationPolicy.can_manage_organization(actor):
            raise ForbiddenException(
                f"Role {actor.role.value} is not permitted to manage an organization"
            )

    @staticmethod
    def can_create_agent_with_role(actor: Agent, role: AgentRole) -> bool:
        if not AuthorizationPolicy.can_manage_organization(actor):
            return False
        # Neither mints through the generic form: ADMIN comes from bootstrap,
        # INTEGRATION only from POST /agents/integration-credential, which
        # generates its own secret instead of accepting one in the body.
        return role not in (AgentRole.ADMIN, AgentRole.INTEGRATION)

    @staticmethod
    def ensure_can_create_agent_with_role(actor: Agent, role: AgentRole) -> None:
        if not AuthorizationPolicy.can_create_agent_with_role(actor, role):
            raise ForbiddenException(f"You may not create an agent with role {role.value}")

    @staticmethod
    def can_list_agents(actor: Agent) -> bool:
        return AuthorizationPolicy.can_manage_organization(actor)

    @staticmethod
    def ensure_can_list_agents(actor: Agent) -> None:
        if not AuthorizationPolicy.can_list_agents(actor):
            raise ForbiddenException("You are not permitted to list agents")

    @staticmethod
    def can_view_lead(
        actor: Agent,
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
        actor: Agent,
        lead_tenant_id: UUID,
        lead_assigned_agent_id: Optional[UUID],
    ) -> None:
        if not AuthorizationPolicy.can_view_lead(actor, lead_tenant_id, lead_assigned_agent_id):
            raise ForbiddenException("You do not have access to this lead")
