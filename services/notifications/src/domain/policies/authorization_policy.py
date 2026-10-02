from typing import Optional, Protocol
from uuid import UUID

from domain.exceptions import ForbiddenException


class Actor(Protocol):
    tenant_id: Optional[UUID]


class AuthorizationPolicy:
    """Who may use the organization plane of this service."""

    @staticmethod
    def ensure_is_organization_member(actor: Actor) -> None:
        # The platform administrator has no organization, so it has no notices either.
        if actor.tenant_id is None:
            raise ForbiddenException("An organization is required to use notifications")
