from dataclasses import dataclass

from domain.entities.agent import Agent
from domain.entities.tenant import Tenant
from domain.events.internal_event import InternalEvent


@dataclass(kw_only=True)
class AgentState(InternalEvent):
    """The agent as other services may know it, after one write.

    A full snapshot, not a diff, so a compacted topic keeps only the latest
    and a consumer drops anything older than the version it already holds.
    Email, password hash and group stay out on purpose: they are not
    identity data any consumer is entitled to."""

    agent_id: str
    name: str
    role: str
    is_active: bool
    version: int

    @property
    def partition_key(self) -> str:
        return self.agent_id

    @classmethod
    def of(cls, agent: Agent) -> "AgentState":
        return cls(
            agent_id=str(agent.id),
            tenant_id=str(agent.tenant_id.value) if agent.tenant_id else None,
            name=agent.name,
            role=agent.role.value,
            is_active=agent.is_active,
            version=agent.version,
        )


@dataclass(kw_only=True)
class TenantState(InternalEvent):
    """The organization after one write; same snapshot semantics as AgentState."""

    tenant_id: str
    name: str
    slug: str
    is_active: bool
    version: int

    @property
    def partition_key(self) -> str:
        return self.tenant_id

    @classmethod
    def of(cls, tenant: Tenant) -> "TenantState":
        return cls(
            tenant_id=str(tenant.id.value),
            name=tenant.name,
            slug=tenant.slug,
            is_active=tenant.is_active,
            version=tenant.version,
        )
