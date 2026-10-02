from uuid import UUID

import psycopg

from application.ports.output.tenants import TenantRepositoryPort
from domain.tenants.tenant import Tenant


def _to_tenant(row) -> Tenant:
    return Tenant.create(
        name=row["name"],
        tenant_id=row["id"],
        slug=row["slug"],
        is_active=row["is_active"],
        created_at=row["created_at"],
        version=row["version"],
    )


class PostgresTenantRepository(TenantRepositoryPort):
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def save(self, tenant: Tenant) -> Tenant:
        row = self.connection.execute(
            """
            INSERT INTO tenants (id, name, slug, is_active, created_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                slug = EXCLUDED.slug,
                is_active = EXCLUDED.is_active,
                version = tenants.version + 1
            RETURNING version
            """,
            (tenant.id.value, tenant.name, tenant.slug, tenant.is_active, tenant.created_at),
        ).fetchone()
        tenant.version = row["version"]
        return tenant

    def get_by_id(self, tenant_id: UUID) -> Tenant | None:
        row = self.connection.execute("SELECT * FROM tenants WHERE id = %s", (tenant_id,)).fetchone()
        return _to_tenant(row) if row else None

    def get_by_slug(self, slug: str) -> Tenant | None:
        row = self.connection.execute("SELECT * FROM tenants WHERE slug = %s", (slug,)).fetchone()
        return _to_tenant(row) if row else None

    def list_all(self, limit: int = 100, offset: int = 0) -> list[Tenant]:
        # id breaks ties between rows created in the same instant, keeping pages stable.
        rows = self.connection.execute(
            "SELECT * FROM tenants ORDER BY created_at DESC, id LIMIT %s OFFSET %s", (limit, offset)
        ).fetchall()
        return [_to_tenant(row) for row in rows]

    def count_all(self) -> int:
        return int(self.connection.execute("SELECT COUNT(*) AS total FROM tenants").fetchone()["total"])

    def count_active_agents(self, tenant_id: UUID) -> int:
        row = self.connection.execute(
            "SELECT COUNT(*) AS total FROM agents WHERE tenant_id = %s AND is_active = TRUE", (tenant_id,)
        ).fetchone()
        return int(row["total"])
