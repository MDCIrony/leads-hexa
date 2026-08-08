from typing import Optional
from uuid import UUID

from domain.entities.agent import Agent
from domain.exceptions import ForbiddenException
from domain.value_objects.enums import AgentRole

_ORGANIZATION_MANAGERS = (AgentRole.ADMIN, AgentRole.MANAGER)


def _same_id(left, right) -> bool:
    """Identifiers arrive as value objects, UUIDs or strings depending on the
    caller, so they are compared by their textual form."""
    return left is not None and right is not None and str(left) == str(right)


class AuthorizationPolicy:
    """Single source of truth for who may do what.

    Lives in the domain so the same rules apply from an HTTP adapter, a CLI or
    a background worker, and so they can be tested without a web framework."""

    @staticmethod
    def can_access_tenant(actor: Agent, tenant_id: UUID) -> bool:
        if actor.role == AgentRole.ADMIN:
            return True
        return _same_id(actor.tenant_id, tenant_id)

    @staticmethod
    def ensure_can_access_tenant(actor: Agent, tenant_id: UUID) -> None:
        if not AuthorizationPolicy.can_access_tenant(actor, tenant_id):
            raise ForbiddenException("You do not have access to this organization's data")

    @staticmethod
    def can_manage_organization(actor: Agent) -> bool:
        return actor.role in _ORGANIZATION_MANAGERS

    @staticmethod
    def ensure_can_manage_organization(actor: Agent) -> None:
        if not AuthorizationPolicy.can_manage_organization(actor):
            raise ForbiddenException(
                f"Role {actor.role.value} is not permitted to perform this action"
            )

    @staticmethod
    def can_create_agent_with_role(actor: Agent, role: AgentRole) -> bool:
        if not AuthorizationPolicy.can_manage_organization(actor):
            return False
        # Only the platform administrator may mint another platform administrator.
        if role == AgentRole.ADMIN:
            return actor.role == AgentRole.ADMIN
        return True

    @staticmethod
    def ensure_can_create_agent_with_role(actor: Agent, role: AgentRole) -> None:
        if not AuthorizationPolicy.can_create_agent_with_role(actor, role):
            raise ForbiddenException(f"You may not create an agent with role {role.value}")

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
