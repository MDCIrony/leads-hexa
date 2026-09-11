from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Response, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse

from application.dtos.context import RequestContext
from application.ports.input.auth_use_case_port import LoginInputPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from application.use_cases.auth_use_cases import MfaUseCase
from infrastructure.adapters.input.api.dependencies import (
    get_current_agent, get_login_use_case, get_mfa_use_case, get_request_context, get_uow,
)
from infrastructure.adapters.input.api.schemas import (
    CurrentUserResponse, LoginResponse, MfaCodeRequest, MfaFactorRequest, MfaPasswordRequest,
    MfaRecoveryCodesResponse, MfaSetupResponse,
)
from domain.entities.agent import Agent
from domain.exceptions import InvalidMfaFactorException

router = APIRouter()


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

    actor = context.actor
    return CurrentUserResponse(
        id=str(actor.id),
        name=actor.name,
        email=actor.email,
        role=actor.role.value,
        tenant_id=str(context.tenant_id) if context.tenant_id else None,
        tenant_name=tenant_name,
        mfa_enabled=bool(enrollment and enrollment.enabled_at),
    )
