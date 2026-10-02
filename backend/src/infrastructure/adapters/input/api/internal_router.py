from fastapi import APIRouter, Depends, Request, Response

from application.ports.output.unit_of_work_port import UnitOfWorkPort
from domain.exceptions import UnauthorizedException
from infrastructure.adapters.input.api.dependencies import (
    get_container, get_uow, resolve_current_agent, resolve_integration_agent,
)
from infrastructure.di.container import Container

router = APIRouter(include_in_schema=False)


@router.get("/auth/introspect")
def introspect(
    request: Request,
    optional: bool = False,
    uow: UnitOfWorkPort = Depends(get_uow),
    container: Container = Depends(get_container),
) -> Response:
    """Says who the caller is, never whether they may do something: that
    stays in each service, on the Principal."""
    api_key = request.headers.get("x-api-key")
    session = request.cookies.get("leads_session")
    # The API key wins over the cookie, and a credential that is present but
    # invalid never degrades to anonymous, even with ?optional=true.
    if api_key:
        agent = resolve_integration_agent(api_key, uow, container.password_hasher)
        principal_type = "integration"
    elif session:
        agent = resolve_current_agent(session, uow)
        principal_type = "human"
    elif optional:
        return Response(status_code=204)
    else:
        raise UnauthorizedException("Authentication required")
    token = container.token_issuer.issue(agent, principal_type)
    return Response(status_code=200, headers={"X-Internal-Token": token})


@router.get("/jwks")
def jwks(container: Container = Depends(get_container)) -> dict:
    return container.jwks
