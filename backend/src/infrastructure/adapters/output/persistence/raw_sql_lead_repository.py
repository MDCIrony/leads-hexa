from typing import List, Optional
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from application.ports.output.lead_repository_port import LeadRepositoryPort
from domain.entities.lead import Lead


class RawSqlLeadRepository(LeadRepositoryPort):
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def save(self, lead: Lead) -> Lead:
        assigned_agent_id = lead.assigned_agent_id.value if lead.assigned_agent_id else None

        sql = """
        INSERT INTO leads (
            id, tenant_id, first_name, last_name, email, company, budget, industry,
            custom_attributes, phone, score, status, assigned_agent_id, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            tenant_id = EXCLUDED.tenant_id,
            first_name = EXCLUDED.first_name,
            last_name = EXCLUDED.last_name,
            email = EXCLUDED.email,
            company = EXCLUDED.company,
            budget = EXCLUDED.budget,
            industry = EXCLUDED.industry,
            custom_attributes = EXCLUDED.custom_attributes,
            phone = EXCLUDED.phone,
            score = EXCLUDED.score,
            status = EXCLUDED.status,
            assigned_agent_id = EXCLUDED.assigned_agent_id,
            created_at = EXCLUDED.created_at
        """
        self.connection.execute(
            sql,
            (
                lead.id.value,
                lead.tenant_id.value,
                lead.first_name,
                lead.last_name,
                str(lead.email),
                lead.company,
                float(lead.budget),
                lead.industry,
                Jsonb(lead.custom_attributes),
                lead.phone,
                int(lead.score),
                lead.status.value,
                assigned_agent_id,
                lead.created_at,
            ),
        )
        return lead

    def _row_to_lead(self, row) -> Lead:
        custom_attrs = row["custom_attributes"]
        return Lead.create(
            lead_id=row["id"],
            tenant_id=row["tenant_id"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            email=row["email"],
            company=row["company"],
            budget=row["budget"],
            industry=row["industry"],
            custom_attributes=custom_attrs,
            phone=row["phone"],
            score=row["score"],
            status=row["status"],
            assigned_agent_id=row["assigned_agent_id"],
            created_at=row["created_at"],
        )

    def get_by_id(self, lead_id: UUID) -> Optional[Lead]:
        cursor = self.connection.execute("SELECT * FROM leads WHERE id = %s", (lead_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_lead(row)

    def list_by_tenant(self, tenant_id: UUID, limit: int = 100, offset: int = 0) -> List[Lead]:
        cursor = self.connection.execute(
            "SELECT * FROM leads WHERE tenant_id = %s LIMIT %s OFFSET %s",
            (tenant_id, limit, offset),
        )
        rows = cursor.fetchall()
        return [self._row_to_lead(row) for row in rows]

    def count_by_tenant(self, tenant_id: UUID) -> int:
        cursor = self.connection.execute(
            "SELECT COUNT(*) AS count FROM leads WHERE tenant_id = %s",
            (tenant_id,),
        )
        row = cursor.fetchone()
        return int(row["count"]) if row else 0
