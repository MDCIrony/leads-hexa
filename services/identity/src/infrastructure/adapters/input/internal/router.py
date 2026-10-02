"""Routes only the Compose network reaches: the gateway answers 404 to any
/internal/ from outside (contracts/openapi/identity-internal.v1.yaml)."""
from uuid import UUID

from chassis.auth import ServiceClaims
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from application.ports.input.agents import GetAgentStateInputPort
from application.ports.input.auth import IntrospectInputPort
from infrastructure.adapters.input.api.auth.cookies import SESSION_COOKIE
from infrastructure.adapters.input.api.dependencies import get_container, get_introspect_use_case, require_agent_reader
from infrastructure.adapters.input.api.use_case_factories import get_get_agent_state_use_case
from infrastructure.di.container import Container
from infrastructure.security.service_token_issuer import ServiceTokenIssuer

router = APIRouter(include_in_schema=False)


class ServiceTokenRequest(BaseModel):
    client_id: str
    client_secret: str
    audience: str


class ServiceTokenResponse(BaseModel):
    access_token: str
    expires_in: int


@router.get("/auth/introspect")
def introspect(
    request: Request,
    optional: bool = False,
    use_case: IntrospectInputPort = Depends(get_introspect_use_case),
    container: Container = Depends(get_container),
) -> Response:
    """Says who the caller is, never whether they may do something: that stays in
    each service, on the Principal."""
    result = use_case.execute(request.headers.get("x-api-key"), request.cookies.get(SESSION_COOKIE), optional)
    if result is None:
        return Response(status_code=204)
    token = container.token_issuer.issue(result.agent, result.principal_type)
    return Response(status_code=200, headers={"X-Internal-Token": token})


@router.get("/jwks")
def jwks(container: Container = Depends(get_container)) -> dict:
    return container.jwks


@router.post("/service-tokens", response_model=ServiceTokenResponse)
def issue_service_token(body: ServiceTokenRequest, container: Container = Depends(get_container)):
    token = container.service_token_issuer.issue(body.client_id, body.client_secret, body.audience)
    return ServiceTokenResponse(access_token=token, expires_in=ServiceTokenIssuer.TTL_SECONDS)


@router.get("/agents/{agent_id}")
def get_agent(
    agent_id: UUID,
    caller: ServiceClaims = Depends(require_agent_reader),
    use_case: GetAgentStateInputPort = Depends(get_get_agent_state_use_case),
) -> dict:
    # The same snapshot AgentState carries, so a hydrated copy and one built from
    # events are indistinguishable (identity.agent.v1).
    return use_case.execute(agent_id).as_payload()
