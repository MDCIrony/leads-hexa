from dataclasses import dataclass
from uuid import UUID

from domain.agents.agent import Agent


@dataclass(frozen=True)
class CreateAgentCommand:
    name: str
    email: str
    password: str
    is_active: bool = True
    role: str = "AGENT"
    tenant_id: UUID | None = None


@dataclass(frozen=True)
class UpdateAgentCommand:
    tenant_id: UUID
    agent_id: UUID
    # None means "leave unchanged", as in every PATCH command.
    name: str | None = None
    is_active: bool | None = None


@dataclass(frozen=True)
class GetAgentsQuery:
    tenant_id: UUID
    # True keeps the default listing to active agents; False lists the deactivated ones, None both.
    is_active: bool | None = True
    limit: int = 100
    offset: int = 0


@dataclass(frozen=True)
class GetAgentQuery:
    tenant_id: UUID
    agent_id: UUID


@dataclass(frozen=True)
class AgentsPageResult:
    items: list[Agent]
    total: int


@dataclass(frozen=True)
class IssueIntegrationCredentialCommand:
    tenant_id: UUID


@dataclass(frozen=True)
class IntegrationCredentialResult:
    agent: Agent
    api_key: str
    kafka_username: str
    kafka_password: str
    kafka_topic: str
