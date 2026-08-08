from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from application.dtos.context import RequestContext
from application.ports.input.auth_use_case_port import LoginInputPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from infrastructure.adapters.input.api.dependencies import (
    get_login_use_case, get_request_context, get_uow,
)
from infrastructure.adapters.input.api.schemas import CurrentUserResponse, LoginResponse

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    use_case: LoginInputPort = Depends(get_login_use_case),
):
    token = use_case.execute(email=form_data.username, password=form_data.password)
    return LoginResponse(access_token=token, token_type="bearer")


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
