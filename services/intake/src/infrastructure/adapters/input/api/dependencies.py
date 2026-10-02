from uuid import UUID

from chassis.auth import KeysUnavailable, TokenError
from fastapi import Depends, Request

from application.dtos.context import Principal, RequestContext
from domain.exceptions import DomainException, ForbiddenException, UnauthorizedException
from domain.policies.authorization_policy import AuthorizationPolicy
from domain.value_objects.agent_role import AgentRole
from infrastructure.di.container import Container


def get_container(request: Request) -> Container:
    return request.app.state.container


def _bearer_token(request: Request) -> str:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise UnauthorizedException()
    return token.strip()


# Sync on purpose: verify() may block on a JWKS fetch under a lock, and FastAPI
# runs sync dependencies in its threadpool, so the event loop stays free.
def get_principal(request: Request, container: Container = Depends(get_container)) -> Principal:
    """The bearer is the gateway's, never the client's: nginx overwrites it."""
    token = _bearer_token(request)
    try:
        claims = container.token_verifier.verify(token)
        return Principal(
            agent_id=UUID(claims.sub),
            tenant_id=UUID(claims.tid) if claims.tid else None,
            role=AgentRole(claims.role),
            principal_type=claims.ptype,
        )
    # Before TokenError: it is a subclass, and an outage is not the caller's fault.
    except KeysUnavailable as error:
        raise DomainException("Signing keys unavailable", error_code="SERVICE_UNAVAILABLE") from error
    except (TokenError, ValueError) as error:
        raise UnauthorizedException() from error


def get_request_context(principal: Principal = Depends(get_principal)) -> RequestContext:
    """A machine credential never stands in for a person here: integrations reach lead-core, not intake."""
    if principal.principal_type == "integration":
        raise UnauthorizedException()
    # The organization comes from the verified identity, never from the path or body.
    return RequestContext(principal=principal, tenant_id=principal.tenant_id)


def require_organization_manager(context: RequestContext = Depends(get_request_context)) -> RequestContext:
    AuthorizationPolicy.ensure_can_manage_organization(context.principal)
    # Identity issues every manager an organization; without one there is nothing to scope the query to.
    if context.tenant_id is None:
        raise ForbiddenException("An organization is required to manage intake")
    return context
