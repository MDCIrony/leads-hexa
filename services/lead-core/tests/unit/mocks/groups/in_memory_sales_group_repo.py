from typing import Dict, List, Optional
from uuid import UUID

from application.ports.output.groups.sales_group_repository_port import SalesGroupRepositoryPort
from domain.groups.sales_group import SalesGroup


class InMemorySalesGroupRepository(SalesGroupRepositoryPort):
    def __init__(self) -> None:
        self.groups: Dict[UUID, SalesGroup] = {}
        # Wired by InMemoryUnitOfWork: deleting a group orphans its advisors,
        # as the foreign key's ON DELETE SET NULL does in Postgres.
        self.advisor_repo = None

    def save(self, group: SalesGroup) -> SalesGroup:
        self.groups[group.id.value] = group
        return group

    def get_by_id(self, group_id: UUID) -> Optional[SalesGroup]:
        return self.groups.get(group_id)

    def list_by_tenant(
        self, tenant_id: UUID, limit: int = 100, offset: int = 0
    ) -> List[SalesGroup]:
        items = [g for g in self.groups.values() if g.tenant_id.value == tenant_id]
        items.sort(key=lambda g: (g.name, str(g.id)))
        return items[offset : offset + limit]

    def count_by_tenant(self, tenant_id: UUID) -> int:
        return len([g for g in self.groups.values() if g.tenant_id.value == tenant_id])

    def delete(self, group_id: UUID) -> None:
        self.groups.pop(group_id, None)
        if self.advisor_repo is not None:
            self.advisor_repo.orphan_group(group_id)
