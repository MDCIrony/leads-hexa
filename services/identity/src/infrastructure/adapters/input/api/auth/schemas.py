from pydantic import BaseModel, Field


class LoginResponse(BaseModel):
    status: str


class OAuthProvidersResponse(BaseModel):
    providers: list[str]


class CurrentUserResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str
    tenant_id: str | None = None
    tenant_name: str | None = None
    mfa_enabled: bool
    linked_oauth_providers: list[str] = Field(default_factory=list)


class MfaPasswordRequest(BaseModel):
    password: str


class MfaCodeRequest(BaseModel):
    code: str


class MfaFactorRequest(BaseModel):
    password: str
    code: str


class MfaSetupResponse(BaseModel):
    secret: str
    otpauth_uri: str


class MfaRecoveryCodesResponse(BaseModel):
    recovery_codes: list[str]
