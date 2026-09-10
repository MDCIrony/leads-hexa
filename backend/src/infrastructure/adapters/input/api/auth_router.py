from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Response, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from application.dtos.context import RequestContext
from application.ports.input.auth_use_case_port import LoginInputPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from infrastructure.adapters.input.api.dependencies import get_login_use_case, get_request_context, get_uow
from infrastructure.adapters.input.api.schemas import CurrentUserResponse, LoginResponse

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    use_case: LoginInputPort = Depends(get_login_use_case),
):
    token = use_case.execute(email=form_data.username, password=form_data.password)
    response = Response(content=LoginResponse(status="AUTHENTICATED").model_dump_json(), media_type="application/json")
    settings = request.app.state.container.settings
    response.set_cookie(
        "leads_session", token, httponly=True, samesite="lax", secure=settings.session_cookie_secure,
        path="/", max_age=settings.session_hours * 3600,
        expires=datetime.now(timezone.utc) + timedelta(hours=settings.session_hours),
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
    return response


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

    actor = context.actor
    return CurrentUserResponse(
        id=str(actor.id),
        name=actor.name,
        email=actor.email,
        role=actor.role.value,
        tenant_id=str(context.tenant_id) if context.tenant_id else None,
        tenant_name=tenant_name,
    )
