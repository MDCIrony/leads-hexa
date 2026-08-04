from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from application.ports.input.auth_use_case_port import LoginInputPort
from infrastructure.adapters.input.api.dependencies import get_login_use_case
from infrastructure.adapters.input.api.schemas import LoginResponse

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    use_case: LoginInputPort = Depends(get_login_use_case),
):
    token = use_case.execute(email=form_data.username, password=form_data.password)
    return LoginResponse(access_token=token, token_type="bearer")
