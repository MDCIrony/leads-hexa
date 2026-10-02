from pydantic import BaseModel, field_validator

from infrastructure.adapters.input.api.agents.schemas import AgentResponse, validate_email_format


class TenantManagerCreate(BaseModel):
    name: str
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return validate_email_format(value)


class TenantCreate(BaseModel):
    name: str
    manager: TenantManagerCreate


class TenantUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None


class TenantResponse(BaseModel):
    id: str
    name: str
    slug: str
    is_active: bool
    created_at: str
    # Absent on some responses by design: the list aggregates a count without
    # identities, the create view has no meaningful count yet.
    agent_count: int | None = None
    manager: AgentResponse | None = None


class PaginatedTenantsResponse(BaseModel):
    items: list[TenantResponse]
    total: int
    limit: int
    offset: int
    has_more: bool
