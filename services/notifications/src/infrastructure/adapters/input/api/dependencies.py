from uuid import UUID

from chassis.auth import KeysUnavailable, TokenError
from fastapi import Depends, Request

from application.dtos.context import Principal, RequestContext
from application.ports.input.notifications import (
    GetNotificationsInputPort,
    MarkAllNotificationsReadInputPort,
    MarkNotificationReadInputPort,
)
from application.use_cases.notifications.list_notifications import GetNotificationsUseCase
from application.use_cases.notifications.mark_read import (
    MarkAllNotificationsReadUseCase,
    MarkNotificationReadUseCase,
)
from domain.exceptions import DomainException
from domain.policies.authorization_policy import AuthorizationPolicy
from infrastructure.di.container import Container

_UNAUTHORIZED = DomainException("Authentication required", error_code="UNAUTHORIZED")


def get_container(request: Request) -> Container:
    return request.app.state.container


def _bearer_token(request: Request) -> str:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise _UNAUTHORIZED
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
            role=claims.role,
            principal_type=claims.ptype,
        )
    # Before TokenError: it is a subclass, and an outage is not the caller's fault.
    except KeysUnavailable as error:
        raise DomainException("Signing keys unavailable", error_code="SERVICE_UNAVAILABLE") from error
    except (TokenError, ValueError) as error:
        raise _UNAUTHORIZED from error


def get_request_context(principal: Principal = Depends(get_principal)) -> RequestContext:
    """A machine credential never stands in for a person."""
    if principal.principal_type == "integration":
        raise _UNAUTHORIZED
    # The organization comes from the verified identity, never from the path or body.
    return RequestContext(principal=principal, tenant_id=principal.tenant_id)


def require_organization_member(context: RequestContext = Depends(get_request_context)) -> RequestContext:
    AuthorizationPolicy.ensure_is_organization_member(context)
    return context


def get_get_notifications_use_case(container: Container = Depends(get_container)) -> GetNotificationsInputPort:
    return GetNotificationsUseCase(uow=container.unit_of_work())


def get_mark_notification_read_use_case(
    container: Container = Depends(get_container),
) -> MarkNotificationReadInputPort:
    return MarkNotificationReadUseCase(uow=container.unit_of_work())


def get_mark_all_notifications_read_use_case(
    container: Container = Depends(get_container),
) -> MarkAllNotificationsReadInputPort:
    return MarkAllNotificationsReadUseCase(uow=container.unit_of_work())
