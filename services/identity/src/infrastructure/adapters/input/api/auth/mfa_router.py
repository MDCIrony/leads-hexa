from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse

from application.ports.input.mfa import MfaEnrollmentInputPort, MfaLoginInputPort
from domain.agents.agent import Agent
from domain.exceptions import InvalidMfaFactorException
from infrastructure.adapters.input.api.auth import cookies
from infrastructure.adapters.input.api.auth.schemas import (
    LoginResponse, MfaCodeRequest, MfaFactorRequest, MfaPasswordRequest, MfaRecoveryCodesResponse, MfaSetupResponse,
)
from infrastructure.adapters.input.api.dependencies import get_container, get_current_agent
from infrastructure.adapters.input.api.use_case_factories import get_mfa_enrollment_use_case, get_mfa_login_use_case
from infrastructure.di.container import Container

router = APIRouter(prefix="/mfa")


@router.post("/verify", response_model=LoginResponse)
def verify_mfa_login(
    request: Request,
    response: Response,
    body: MfaCodeRequest,
    use_case: MfaLoginInputPort = Depends(get_mfa_login_use_case),
    container: Container = Depends(get_container),
):
    try:
        result = use_case.verify_login(request.cookies.get(cookies.MFA_CHALLENGE_COOKIE), body.code)
    except InvalidMfaFactorException as error:
        # Answered here, not by the handler: only this route knows whether the
        # challenge is spent and its cookie must go.
        failure = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"error": True, "error_code": error.error_code, "message": error.message},
        )
        if error.terminal:
            cookies.clear_mfa_challenge(failure)
        return failure
    cookies.apply_login(response, result, container.settings)
    return LoginResponse(status=result.status)


@router.post("/setup", response_model=MfaSetupResponse)
def setup_mfa(
    body: MfaPasswordRequest,
    agent: Agent = Depends(get_current_agent),
    use_case: MfaEnrollmentInputPort = Depends(get_mfa_enrollment_use_case),
):
    result = use_case.setup(agent, body.password)
    return MfaSetupResponse(secret=result.secret, otpauth_uri=result.otpauth_uri)


@router.post("/setup/confirm", response_model=MfaRecoveryCodesResponse)
def confirm_mfa_setup(
    request: Request,
    body: MfaCodeRequest,
    agent: Agent = Depends(get_current_agent),
    use_case: MfaEnrollmentInputPort = Depends(get_mfa_enrollment_use_case),
):
    # get_current_agent already proved the cookie is there.
    session = request.cookies[cookies.SESSION_COOKIE]
    return MfaRecoveryCodesResponse(recovery_codes=use_case.confirm(agent, session, body.code))


@router.post("/recovery-codes/regenerate", response_model=MfaRecoveryCodesResponse)
def regenerate_recovery_codes(
    body: MfaFactorRequest,
    agent: Agent = Depends(get_current_agent),
    use_case: MfaEnrollmentInputPort = Depends(get_mfa_enrollment_use_case),
):
    return MfaRecoveryCodesResponse(recovery_codes=use_case.regenerate_recovery_codes(agent, body.password, body.code))


@router.post("/disable", status_code=status.HTTP_204_NO_CONTENT)
def disable_mfa(
    request: Request,
    body: MfaFactorRequest,
    agent: Agent = Depends(get_current_agent),
    use_case: MfaEnrollmentInputPort = Depends(get_mfa_enrollment_use_case),
) -> Response:
    use_case.disable(agent, request.cookies.get(cookies.SESSION_COOKIE), body.password, body.code)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
