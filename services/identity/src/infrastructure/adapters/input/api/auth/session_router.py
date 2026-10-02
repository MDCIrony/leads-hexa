from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from application.ports.input.auth import CurrentIdentityInputPort, LoginInputPort, LogoutInputPort
from domain.agents.agent import Agent
from infrastructure.adapters.input.api.auth import cookies
from infrastructure.adapters.input.api.auth.schemas import CurrentUserResponse, LoginResponse
from infrastructure.adapters.input.api.dependencies import get_container, get_current_agent
from infrastructure.adapters.input.api.use_case_factories import (
    get_current_identity_use_case, get_login_use_case, get_logout_use_case,
)
from infrastructure.di.container import Container

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    use_case: LoginInputPort = Depends(get_login_use_case),
    container: Container = Depends(get_container),
):
    # The token travels only in the HttpOnly cookie, never in the body.
    result = use_case.execute(email=form_data.username, password=form_data.password)
    cookies.apply_login(response, result, container.settings)
    return LoginResponse(status=result.status)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, use_case: LogoutInputPort = Depends(get_logout_use_case)) -> Response:
    # Idempotent: an anonymous or already revoked logout still clears the browser.
    use_case.execute(request.cookies.get(cookies.SESSION_COOKIE))
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    cookies.clear_session(response)
    cookies.clear_mfa_challenge(response)
    return response


@router.get("/me", response_model=CurrentUserResponse)
def get_current_user(
    agent: Agent = Depends(get_current_agent),
    use_case: CurrentIdentityInputPort = Depends(get_current_identity_use_case),
):
    identity = use_case.execute(agent)
    return CurrentUserResponse(
        id=str(agent.id),
        name=agent.name,
        email=agent.email,
        role=agent.role.value,
        tenant_id=str(agent.tenant_id) if agent.tenant_id else None,
        tenant_name=identity.tenant_name,
        mfa_enabled=identity.mfa_enabled,
        linked_oauth_providers=identity.linked_oauth_providers,
    )
