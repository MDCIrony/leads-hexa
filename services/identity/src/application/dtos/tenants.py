from dataclasses import dataclass
from uuid import UUID

from domain.agents.agent import Agent
from domain.tenants.tenant import Tenant


@dataclass(frozen=True)
class CreateTenantCommand:
    name: str
    manager_name: str
    manager_email: str
    manager_password: str


@dataclass(frozen=True)
class UpdateTenantCommand:
    tenant_id: UUID
    name: str | None = None
    is_active: bool | None = None


@dataclass(frozen=True)
class GetTenantsQuery:
    limit: int = 100
    offset: int = 0


@dataclass(frozen=True)
class TenantWithManagerResult:
    tenant: Tenant
    manager: Agent


@dataclass(frozen=True)
class TenantSummary:
    tenant: Tenant
    agent_count: int


@dataclass(frozen=True)
class TenantsPageResult:
    items: list[TenantSummary]
    total: int
