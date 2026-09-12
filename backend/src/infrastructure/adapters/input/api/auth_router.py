from base64 import urlsafe_b64encode
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse, RedirectResponse

from application.dtos.context import RequestContext
from application.ports.input.auth_use_case_port import LoginInputPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from application.use_cases.auth_use_cases import MfaUseCase, OAuthChallengeUseCase, SocialLoginUseCase
from infrastructure.adapters.input.api.dependencies import (
    get_current_agent, get_login_use_case, get_mfa_use_case, get_oauth_challenge_use_case,
    get_request_context, get_social_login_use_case, get_uow,
)
from infrastructure.adapters.input.api.schemas import (
    CurrentUserResponse, LoginResponse, MfaCodeRequest, MfaFactorRequest, MfaPasswordRequest,
    MfaRecoveryCodesResponse, MfaSetupResponse, OAuthProvidersResponse,
)
from domain.entities.agent import Agent
from domain.exceptions import InvalidCredentialsException, InvalidMfaFactorException

router = APIRouter()

_OAUTH_AUTHORIZATION = {
    "GOOGLE": ("https://accounts.google.com/o/oauth2/v2/auth", "openid email profile"),
    "GITHUB": ("https://github.com/login/oauth/authorize", "read:user user:email"),
}


def _oauth_provider(value: str) -> str:
    provider = value.upper()
    if provider not in _OAUTH_AUTHORIZATION:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proveedor no disponible")
    return provider


def _oauth_callback_error(request: Request) -> RedirectResponse:
    response = RedirectResponse(
        f"{request.app.state.container.settings.frontend_origin}/login?oauth_error=1",
        status_code=status.HTTP_303_SEE_OTHER,
    )
    response.delete_cookie("leads_oauth_challenge", path="/api/v1/auth/oauth")
    return response


@router.get("/oauth/providers", response_model=OAuthProvidersResponse)
def oauth_providers(request: Request, response: Response):
    # Dynamic per configuration: a cached "[]" would hide buttons that a
    # later-configured provider should show.
    response.headers["Cache-Control"] = "no-store"
    return OAuthProvidersResponse(providers=request.app.state.container.oauth_providers)


@router.get(
    "/oauth/{provider}/start", status_code=status.HTTP_303_SEE_OTHER,
    response_class=RedirectResponse, responses={303: {"description": "Redirección al proveedor OAuth"}},
)
def start_oauth_login(
    provider: str,
    request: Request,
    return_path: str = "/",
    use_case: OAuthChallengeUseCase = Depends(get_oauth_challenge_use_case),
):
    normalized_provider = _oauth_provider(provider)
    container = request.app.state.container
    identity_provider = container.oauth_identity_provider(normalized_provider)
    if identity_provider is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proveedor no disponible")
    try:
        challenge = use_case.start(normalized_provider, return_path)
    except InvalidCredentialsException:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ruta de retorno inválida") from None

    endpoint, scope = _OAUTH_AUTHORIZATION[normalized_provider]
    settings = container.settings.google_oauth if normalized_provider == "GOOGLE" else container.settings.github_oauth
    code_challenge = urlsafe_b64encode(sha256(challenge.pkce_verifier.encode()).digest()).rstrip(b"=").decode()
    parameters = urlencode({
        "response_type": "code", "client_id": settings.client_id,
        "redirect_uri": settings.redirect_uri, "scope": scope, "state": challenge.state,
        "code_challenge": code_challenge, "code_challenge_method": "S256",
    })
    response = RedirectResponse(
        f"{endpoint}?{parameters}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
    response.set_cookie(
        "leads_oauth_challenge", challenge.nonce, httponly=True, samesite="lax",
        secure=container.settings.session_cookie_secure, path="/api/v1/auth/oauth", max_age=300,
        expires=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    return response


@router.get(
    "/oauth/{provider}/callback", status_code=status.HTTP_303_SEE_OTHER,
    response_class=RedirectResponse, responses={303: {"description": "Redirección tras OAuth"}},
)
def oauth_callback(
    provider: str,
    request: Request,
    code: str | None = None,
    state: str | None = None,
    challenge_use_case: OAuthChallengeUseCase = Depends(get_oauth_challenge_use_case),
    social_login: SocialLoginUseCase = Depends(get_social_login_use_case),
):
    try:
        normalized_provider = _oauth_provider(provider)
        container = request.app.state.container
        identity_provider = container.oauth_identity_provider(normalized_provider)
        if identity_provider is None or not code:
            raise InvalidMfaFactorException(terminal=True)
        challenge = challenge_use_case.consume(
            request.cookies.get("leads_oauth_challenge"), normalized_provider, state
        )
        identity = identity_provider.exchange(code, challenge.pkce_verifier or "")
        result = social_login.execute(
            normalized_provider, identity.provider_subject, identity.email, identity.email_verified,
        )
    except Exception:
        return _oauth_callback_error(request)

    settings = request.app.state.container.settings
    if result.status == "MFA_REQUIRED":
        response = RedirectResponse(
            f"{settings.frontend_origin}/mfa", status_code=status.HTTP_303_SEE_OTHER,
        )
        response.delete_cookie("leads_session", path="/")
        response.set_cookie(
            "leads_mfa_challenge", result.token, httponly=True, samesite="lax",
            secure=settings.session_cookie_secure, path="/api/v1/auth/mfa", max_age=300,
            expires=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
    else:
        response = RedirectResponse(
            f"{settings.frontend_origin}{challenge.return_path}", status_code=status.HTTP_303_SEE_OTHER,
        )
        response.delete_cookie("leads_mfa_challenge", path="/api/v1/auth/mfa")
        response.set_cookie(
            "leads_session", result.token, httponly=True, samesite="lax", secure=settings.session_cookie_secure,
            path="/", max_age=settings.session_hours * 3600,
            expires=datetime.now(timezone.utc) + timedelta(hours=settings.session_hours),
        )
    response.delete_cookie("leads_oauth_challenge", path="/api/v1/auth/oauth")
    return response


@router.post("/login", response_model=LoginResponse)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    use_case: LoginInputPort = Depends(get_login_use_case),
):
    result = use_case.execute(email=form_data.username, password=form_data.password)
    response = Response(content=LoginResponse(status=result.status).model_dump_json(), media_type="application/json")
    settings = request.app.state.container.settings
    response.delete_cookie("leads_mfa_challenge", path="/api/v1/auth/mfa")
    if result.status == "AUTHENTICATED":
        response.set_cookie(
            "leads_session", result.token, httponly=True, samesite="lax", secure=settings.session_cookie_secure,
            path="/", max_age=settings.session_hours * 3600,
            expires=datetime.now(timezone.utc) + timedelta(hours=settings.session_hours),
        )
    else:
        response.delete_cookie("leads_session", path="/")
        response.set_cookie(
            "leads_mfa_challenge", result.token, httponly=True, samesite="lax", secure=settings.session_cookie_secure,
            path="/api/v1/auth/mfa", max_age=300,
            expires=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
    return response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, uow: UnitOfWorkPort = Depends(get_uow)):
    token = request.cookies.get("leads_session")
    if token:
        from hashlib import sha256
        with uow:
            uow.sessions.revoke(sha256(token.encode()).hexdigest(), datetime.now(timezone.utc))
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie("leads_session", path="/")
    response.delete_cookie("leads_mfa_challenge", path="/api/v1/auth/mfa")
    return response


@router.post("/mfa/verify", response_model=LoginResponse)
def verify_mfa_login(
    request: Request,
    body: MfaCodeRequest,
    use_case: MfaUseCase = Depends(get_mfa_use_case),
):
    try:
        result = use_case.verify_login(request.cookies.get("leads_mfa_challenge"), body.code)
    except InvalidMfaFactorException as error:
        response = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"error": True, "error_code": error.error_code, "message": error.message},
        )
        if error.terminal:
            response.delete_cookie("leads_mfa_challenge", path="/api/v1/auth/mfa")
        return response
    settings = request.app.state.container.settings
    response = Response(content=LoginResponse(status=result.status).model_dump_json(), media_type="application/json")
    response.set_cookie(
        "leads_session", result.token, httponly=True, samesite="lax", secure=settings.session_cookie_secure,
        path="/", max_age=settings.session_hours * 3600,
        expires=datetime.now(timezone.utc) + timedelta(hours=settings.session_hours),
    )
    response.delete_cookie("leads_mfa_challenge", path="/api/v1/auth/mfa")
    return response


@router.post("/mfa/setup", response_model=MfaSetupResponse)
def setup_mfa(
    body: MfaPasswordRequest,
    agent: Agent = Depends(get_current_agent),
    use_case: MfaUseCase = Depends(get_mfa_use_case),
):
    result = use_case.setup(agent, body.password)
    return MfaSetupResponse(secret=result.secret, otpauth_uri=result.otpauth_uri)


@router.post("/mfa/setup/confirm", response_model=MfaRecoveryCodesResponse)
def confirm_mfa_setup(
    request: Request,
    body: MfaCodeRequest,
    agent: Agent = Depends(get_current_agent),
    use_case: MfaUseCase = Depends(get_mfa_use_case),
):
    return MfaRecoveryCodesResponse(
        recovery_codes=use_case.confirm(agent, request.cookies["leads_session"], body.code)
    )


@router.post("/mfa/recovery-codes/regenerate", response_model=MfaRecoveryCodesResponse)
def regenerate_recovery_codes(
    body: MfaFactorRequest,
    agent: Agent = Depends(get_current_agent),
    use_case: MfaUseCase = Depends(get_mfa_use_case),
):
    return MfaRecoveryCodesResponse(
        recovery_codes=use_case.regenerate_recovery_codes(agent, body.password, body.code)
    )


@router.post("/mfa/disable", status_code=status.HTTP_204_NO_CONTENT)
def disable_mfa(
    request: Request,
    body: MfaFactorRequest,
    agent: Agent = Depends(get_current_agent),
    use_case: MfaUseCase = Depends(get_mfa_use_case),
):
    use_case.disable(agent, request.cookies.get("leads_session"), body.password, body.code)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=CurrentUserResponse)
def get_current_user(
    context: RequestContext = Depends(get_request_context),
    uow: UnitOfWorkPort = Depends(get_uow),
):
    tenant_name = None
    if context.tenant_id is not None:
        with uow:
            tenant = uow.tenants.get_by_id(context.tenant_id)
        tenant_name = tenant.name if tenant else None

    with uow:
        enrollment = uow.mfa.get(context.actor.id.value)
        linked_oauth_providers = [
            identity.provider for identity in uow.social_identities.list_by_agent(context.actor.id.value)
        ]

    actor = context.actor
    return CurrentUserResponse(
        id=str(actor.id),
        name=actor.name,
        email=actor.email,
        role=actor.role.value,
        tenant_id=str(context.tenant_id) if context.tenant_id else None,
        tenant_name=tenant_name,
        mfa_enabled=bool(enrollment and enrollment.enabled_at),
        linked_oauth_providers=linked_oauth_providers,
    )
