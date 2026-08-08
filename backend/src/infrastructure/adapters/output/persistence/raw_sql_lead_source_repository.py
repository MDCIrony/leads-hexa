from typing import List, Optional
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from application.ports.output.lead_source_repository_port import LeadSourceRepositoryPort
from domain.entities.lead_source import LeadSource
from domain.value_objects.enums import LeadSourceKind


class RawSqlLeadSourceRepository(LeadSourceRepositoryPort):
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def save(self, source: LeadSource) -> LeadSource:
        self.connection.execute(
            """
            INSERT INTO lead_sources (
                id, tenant_id, name, kind, field_mapping, is_active, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                kind = EXCLUDED.kind,
                field_mapping = EXCLUDED.field_mapping,
                is_active = EXCLUDED.is_active,
                updated_at = EXCLUDED.updated_at
            """,
            (
                source.id.value,
                source.tenant_id.value,
                source.name,
                source.kind.value,
                Jsonb(source.field_mapping),
                source.is_active,
                source.created_at,
                source.updated_at,
            ),
        )
        return source

    def get_by_id_and_tenant(self, source_id: UUID, tenant_id: UUID) -> Optional[LeadSource]:
        row = self.connection.execute(
            "SELECT * FROM lead_sources WHERE id = %s AND tenant_id = %s",
            (source_id, tenant_id),
        ).fetchone()
        return self._row_to_source(row) if row else None

    def get_by_kind(self, tenant_id: UUID, kind: LeadSourceKind) -> Optional[LeadSource]:
        # Oldest first: the automatic source CreateTenantUseCase provisions at
        # tenant creation is the one the unified intake pipeline resolves to.
        row = self.connection.execute(
            "SELECT * FROM lead_sources WHERE tenant_id = %s AND kind = %s ORDER BY created_at LIMIT 1",
            (tenant_id, kind.value),
        ).fetchone()
        return self._row_to_source(row) if row else None

    def list_by_tenant(self, tenant_id: UUID, limit: int = 100, offset: int = 0) -> List[LeadSource]:
        rows = self.connection.execute(
            "SELECT * FROM lead_sources WHERE tenant_id = %s ORDER BY name, id LIMIT %s OFFSET %s",
            (tenant_id, limit, offset),
        ).fetchall()
        return [self._row_to_source(row) for row in rows]

    def delete(self, source_id: UUID, tenant_id: UUID) -> bool:
        cursor = self.connection.execute(
            "DELETE FROM lead_sources WHERE id = %s AND tenant_id = %s",
            (source_id, tenant_id),
        )
        return cursor.rowcount > 0

    @staticmethod
    def _row_to_source(row) -> LeadSource:
        return LeadSource.create(
            source_id=row["id"],
            tenant_id=row["tenant_id"],
            name=row["name"],
            kind=row["kind"],
            field_mapping=row["field_mapping"],
            is_active=row["is_active"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
