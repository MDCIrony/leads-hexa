from uuid import UUID

import psycopg

from application.ports.output.intake.provisioned_tenant_repository_port import ProvisionedTenantRepositoryPort


class RawSqlProvisionedTenantRepository(ProvisionedTenantRepositoryPort):
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def mark(self, tenant_id: UUID) -> bool:
        cursor = self.connection.execute(
            "INSERT INTO provisioned_tenants (tenant_id) VALUES (%s) ON CONFLICT (tenant_id) DO NOTHING",
            (tenant_id,),
        )
        return cursor.rowcount == 1
