from collections.abc import Callable
from typing import Optional, TypeVar
from uuid import UUID

from chassis.auth import KeysUnavailable, ServiceClaims, TokenError
from fastapi import Depends, Request

from application.dtos.context import Principal, RequestContext
from application.ports.input.auth import IntrospectInputPort
from application.ports.output.unit_of_work import UnitOfWorkPort
from application.use_cases.auth.introspect import IntrospectUseCase
from domain.agents.agent import Agent
from domain.exceptions import DomainException, UnauthorizedException
from domain.policies.authorization_policy import AuthorizationPolicy
from domain.value_objects.agent_role import AgentRole
from infrastructure.adapters.input.api.auth.cookies import SESSION_COOKIE
from infrastructure.di.container import Container

_T = TypeVar("_T")

# The only service allowed to read an agent through /internal/v1/agents/{agent_id}.
AGENT_READERS = frozenset({"lead-core"})


def get_container(request: Request) -> Container:
    return request.app.state.container


def get_uow(container: Container = Depends(get_container)) -> UnitOfWorkPort:
    return container.unit_of_work()


def _bearer_token(request: Request) -> Optional[str]:
    header = request.headers.get("authorization")
    if not header:
        return None
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer":
        raise UnauthorizedException("Authentication required")
    return token.strip() or None


def _verified(verify: Callable[[], _T]) -> _T:
    try:
        return verify()
    # Before TokenError: it is a subclass, and an outage is not the caller's fault.
    except KeysUnavailable as error:
        raise DomainException("Signing keys unavailable", error_code="SERVICE_UNAVAILABLE") from error
    except (TokenError, ValueError) as error:
        raise UnauthorizedException("Authentication required") from error


def _principal_from_token(token: str, container: Container) -> Principal:
    def verify() -> Principal:
        claims = container.token_verifier.verify(token)
        return Principal(
            id=UUID(claims.sub),
            tenant_id=UUID(claims.tid) if claims.tid else None,
            role=AgentRole(claims.role),
            principal_type=claims.ptype,
        )

    return _verified(verify)


# Sync on purpose, like every dependency here: FastAPI runs them in its threadpool.
def get_principal(request: Request, container: Container = Depends(get_container)) -> Principal:
    """The bearer is the gateway's, never the client's: nginx overwrites it."""
    token = _bearer_token(request)
    if token is None:
        raise UnauthorizedException("Authentication required")
    return _principal_from_token(token, container)


def get_optional_principal(
    request: Request, container: Container = Depends(get_container)
) -> Optional[Principal]:
    """None only when no bearer arrives; a bearer that fails verification is 401."""
    token = _bearer_token(request)
    return None if token is None else _principal_from_token(token, container)


def get_optional_human_principal(
    principal: Optional[Principal] = Depends(get_optional_principal),
) -> Optional[Principal]:
    """A machine credential never stands in for a person, not even on a route open to anonymous callers."""
    if principal is not None and principal.principal_type == "integration":
        raise UnauthorizedException("Authentication required")
    return principal


def build_request_context(principal: Principal) -> RequestContext:
    # The organization comes from the verified identity, never from the path or body.
    return RequestContext(principal=principal, tenant_id=principal.tenant_id)


def get_request_context(principal: Principal = Depends(get_principal)) -> RequestContext:
    if principal.principal_type == "integration":
        raise UnauthorizedException("Authentication required")
    return build_request_context(principal)


def require_organization_manager(context: RequestContext = Depends(get_request_context)) -> RequestContext:
    AuthorizationPolicy.ensure_can_manage_organization(context.principal)
    return context


def require_platform_admin(context: RequestContext = Depends(get_request_context)) -> RequestContext:
    AuthorizationPolicy.ensure_can_manage_platform(context.principal)
    return context


def get_introspect_use_case(
    uow: UnitOfWorkPort = Depends(get_uow), container: Container = Depends(get_container)
) -> IntrospectInputPort:
    return IntrospectUseCase(uow=uow, password_hasher=container.password_hasher)


def get_current_agent(
    request: Request, introspect: IntrospectInputPort = Depends(get_introspect_use_case)
) -> Agent:
    """The signed-in person behind the session cookie, for the /auth routes the gateway
    forwards without introspecting. Same checks as the introspection itself."""
    return introspect.execute(None, request.cookies.get(SESSION_COOKIE)).agent


def require_agent_reader(request: Request, container: Container = Depends(get_container)) -> ServiceClaims:
    token = _bearer_token(request)
    if token is None:
        raise UnauthorizedException("Authentication required")
    return _verified(lambda: container.service_token_verifier.verify(token, AGENT_READERS))
