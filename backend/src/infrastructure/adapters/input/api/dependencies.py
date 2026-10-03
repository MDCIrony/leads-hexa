from typing import Optional
from uuid import UUID
from fastapi import Request, Depends
from chassis.auth import KeysUnavailable, TokenError
from application.dtos.context import Principal, RequestContext
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from domain.exceptions import DomainException, UnauthorizedException
from domain.policies.authorization_policy import AuthorizationPolicy
from domain.value_objects.enums import AgentRole
from infrastructure.di.container import Container

def get_container(request: Request) -> Container:
    return request.app.state.container

def get_uow(container: Container = Depends(get_container)) -> UnitOfWorkPort:
    return container.unit_of_work()

def build_request_context(principal: Principal) -> RequestContext:
    """The organization always comes from the verified identity, never from the
    request path or body."""
    return RequestContext(principal=principal, tenant_id=principal.tenant_id)


def bearer_token(request: Request) -> Optional[str]:
    header = request.headers.get("authorization")
    if not header:
        return None
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer":
        raise UnauthorizedException("Authentication required")
    return token.strip() or None


def _principal_from_token(token: str, container: Container) -> Principal:
    try:
        claims = container.token_verifier.verify(token)
        return Principal(
            id=UUID(claims.sub),
            tenant_id=UUID(claims.tid) if claims.tid else None,
            role=AgentRole(claims.role),
            principal_type=claims.ptype,
        )
    except KeysUnavailable as error:  # before TokenError, its parent: an outage is not the caller's fault
        raise DomainException("Signing keys unavailable", error_code="SERVICE_UNAVAILABLE") from error
    except (TokenError, ValueError) as error:
        raise UnauthorizedException("Authentication required") from error


def get_principal(request: Request, container: Container = Depends(get_container)) -> Principal:
    """The bearer is the gateway's, never the client's: nginx overwrites it."""
    token = bearer_token(request)
    if token is None:
        raise UnauthorizedException("Authentication required")
    return _principal_from_token(token, container)


def get_request_context(principal: Principal = Depends(get_principal)) -> RequestContext:
    """Rejects ptype=integration: a machine credential reaches only the route
    that composes require_manager_or_integration."""
    if principal.principal_type == "integration":
        raise UnauthorizedException("Authentication required")
    return build_request_context(principal)


def require_organization_manager(
    context: RequestContext = Depends(get_request_context),
) -> RequestContext:
    AuthorizationPolicy.ensure_can_manage_organization(context.principal)
    return context


def require_organization_member(
    context: RequestContext = Depends(get_request_context),
) -> RequestContext:
    """Any member of an organization: manager or sales agent.

    The platform admin has no tenant, so it is excluded by construction —
    which is the point: it must not reach operational data."""
    AuthorizationPolicy.ensure_can_access_tenant(context.principal, context.tenant_id)
    return context


def require_manager_or_integration(principal: Principal = Depends(get_principal)) -> RequestContext:
    """Composes the two authentication paths at exactly one route (GET
    /leads) instead of branching inside a shared handler — authorization by
    routing, the same shape require_organization_member vs.
    require_organization_manager already use."""
    if principal.principal_type != "integration":
        AuthorizationPolicy.ensure_can_manage_organization(principal)
    return build_request_context(principal)
