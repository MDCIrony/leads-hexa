from pydantic import BaseModel, ConfigDict, field_validator

from domain.agents.agent import Agent
from domain.value_objects.agent_role import AgentRole


def validate_email_format(value: str) -> str:
    if "@" not in value or "." not in value.split("@")[-1]:
        raise ValueError("Formato de email inválido")
    return value


class AgentCreate(BaseModel):
    # Forbid, not ignore: a client still sending group_id must learn that grouping
    # moved to the leads side instead of seeing it silently dropped.
    model_config = ConfigDict(extra="forbid")

    name: str
    email: str
    is_active: bool = True
    password: str
    role: AgentRole = AgentRole.AGENT
    # No tenant_id: the organization is always the caller's own, from the token.

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return validate_email_format(value)


class AgentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    # None means unchanged; True reactivates, False deactivates (same as DELETE).
    is_active: bool | None = None


class AgentResponse(BaseModel):
    id: str
    name: str
    email: str
    is_active: bool
    role: str
    tenant_id: str | None = None


class PaginatedAgentsResponse(BaseModel):
    items: list[AgentResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class IntegrationCredentialResponse(BaseModel):
    """Deliberately not AgentResponse plus a field: these secrets must never be
    echoed back by GET /agents/{agent_id}."""

    agent_id: str
    tenant_id: str
    api_key: str
    kafka_username: str
    kafka_password: str
    kafka_bootstrap_servers: str
    kafka_topic: str


def to_agent_response(agent: Agent) -> AgentResponse:
    return AgentResponse(
        id=str(agent.id),
        name=agent.name,
        email=agent.email,
        is_active=agent.is_active,
        role=agent.role.value,
        tenant_id=str(agent.tenant_id) if agent.tenant_id else None,
    )
