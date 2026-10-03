from typing import List, Optional
from uuid import UUID

import psycopg

from application.ports.output.groups.sales_group_repository_port import SalesGroupRepositoryPort
from domain.groups.sales_group import SalesGroup


class RawSqlSalesGroupRepository(SalesGroupRepositoryPort):
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def save(self, group: SalesGroup) -> SalesGroup:
        self.connection.execute(
            """
            INSERT INTO sales_groups (
                id, tenant_id, name, description, default_strategy,
                capacity_per_agent, is_active, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                default_strategy = EXCLUDED.default_strategy,
                capacity_per_agent = EXCLUDED.capacity_per_agent,
                is_active = EXCLUDED.is_active
            """,
            (
                group.id.value,
                group.tenant_id.value,
                group.name,
                group.description,
                group.default_strategy.value,
                group.capacity_per_agent,
                group.is_active,
                group.created_at,
            ),
        )
        return group

    def get_by_id(self, group_id: UUID) -> Optional[SalesGroup]:
        row = self.connection.execute(
            "SELECT * FROM sales_groups WHERE id = %s", (group_id,)
        ).fetchone()
        return self._to_group(row) if row else None

    def list_by_tenant(
        self, tenant_id: UUID, limit: int = 100, offset: int = 0
    ) -> List[SalesGroup]:
        rows = self.connection.execute(
            "SELECT * FROM sales_groups WHERE tenant_id = %s ORDER BY name, id LIMIT %s OFFSET %s",
            (tenant_id, limit, offset),
        ).fetchall()
        return [self._to_group(row) for row in rows]

    def count_by_tenant(self, tenant_id: UUID) -> int:
        row = self.connection.execute(
            "SELECT COUNT(*) AS count FROM sales_groups WHERE tenant_id = %s", (tenant_id,)
        ).fetchone()
        return int(row["count"])

    def delete(self, group_id: UUID) -> None:
        # Agents pointing at this group are not touched here: the foreign
        # key (ON DELETE SET NULL, migration 003) orphans them instead.
        self.connection.execute("DELETE FROM sales_groups WHERE id = %s", (group_id,))

    @staticmethod
    def _to_group(row) -> SalesGroup:
        return SalesGroup.create(
            group_id=row["id"],
            tenant_id=row["tenant_id"],
            name=row["name"],
            description=row["description"],
            default_strategy=row["default_strategy"],
            capacity_per_agent=row["capacity_per_agent"],
            is_active=row["is_active"],
            created_at=row["created_at"],
        )
