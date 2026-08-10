from typing import List, Optional
from uuid import UUID

from application.ports.output.tenant_repository_port import TenantRepositoryPort
from domain.entities.tenant import Tenant


class RawSqlTenantRepository(TenantRepositoryPort):
    def __init__(self, connection) -> None:
        self.connection = connection

    def save(self, tenant: Tenant) -> Tenant:
        self.connection.execute(
            """
            INSERT INTO tenants (id, name, slug, is_active, created_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                slug = EXCLUDED.slug,
                is_active = EXCLUDED.is_active
            """,
            (
                tenant.id.value,
                tenant.name,
                tenant.slug,
                tenant.is_active,
                tenant.created_at,
            ),
        )
        return tenant

    def get_by_id(self, tenant_id: UUID) -> Optional[Tenant]:
        row = self.connection.execute(
            "SELECT * FROM tenants WHERE id = %s", (tenant_id,)
        ).fetchone()
        return self._to_tenant(row) if row else None

    def get_by_slug(self, slug: str) -> Optional[Tenant]:
        row = self.connection.execute(
            "SELECT * FROM tenants WHERE slug = %s", (slug,)
        ).fetchone()
        return self._to_tenant(row) if row else None

    def list_all(self, limit: int = 100, offset: int = 0) -> List[Tenant]:
        # Newest organization first, matching GET /leads and GET /notifications.
        # Ordering by id as a tiebreaker keeps pages stable when two rows share
        # a creation timestamp.
        rows = self.connection.execute(
            "SELECT * FROM tenants ORDER BY created_at DESC, id LIMIT %s OFFSET %s",
            (limit, offset),
        ).fetchall()
        return [self._to_tenant(row) for row in rows]

    def count_all(self) -> int:
        row = self.connection.execute("SELECT COUNT(*) AS count FROM tenants").fetchone()
        return int(row["count"])

    def count_active_agents(self, tenant_id: UUID) -> int:
        row = self.connection.execute(
            "SELECT COUNT(*) AS count FROM agents WHERE tenant_id = %s AND is_active = TRUE",
            (tenant_id,),
        ).fetchone()
        return int(row["count"])

    @staticmethod
    def _to_tenant(row) -> Tenant:
        return Tenant.create(
            name=row["name"],
            tenant_id=row["id"],
            slug=row["slug"],
            is_active=row["is_active"],
            created_at=row["created_at"],
        )
