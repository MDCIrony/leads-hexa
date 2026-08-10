from typing import Dict, List, Optional
from uuid import UUID

from application.ports.output.tenant_repository_port import TenantRepositoryPort
from domain.entities.tenant import Tenant


class InMemoryTenantRepository(TenantRepositoryPort):
    def __init__(self) -> None:
        self._tenants: Dict[str, Tenant] = {}
        self._agent_counts: Dict[str, int] = {}

    def save(self, tenant: Tenant) -> Tenant:
        self._tenants[str(tenant.id)] = tenant
        return tenant

    def get_by_id(self, tenant_id: UUID) -> Optional[Tenant]:
        return self._tenants.get(str(tenant_id))

    def get_by_slug(self, slug: str) -> Optional[Tenant]:
        return next((t for t in self._tenants.values() if t.slug == slug), None)

    def list_all(self, limit: int = 100, offset: int = 0) -> List[Tenant]:
        # Matches "ORDER BY created_at DESC, id": id stays ascending as the
        # tiebreaker, so two stable sorts (id first, then created_at desc).
        ordered = sorted(self._tenants.values(), key=lambda t: str(t.id))
        ordered.sort(key=lambda t: t.created_at, reverse=True)
        return ordered[offset : offset + limit]

    def count_all(self) -> int:
        return len(self._tenants)

    def count_active_agents(self, tenant_id: UUID) -> int:
        return self._agent_counts.get(str(tenant_id), 0)

    def set_agent_count(self, tenant_id: UUID, count: int) -> None:
        """Test seam: lets a test state the aggregate without wiring an agent
        repository into it."""
        self._agent_counts[str(tenant_id)] = count
