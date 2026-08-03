import json
from typing import List, Optional
from uuid import UUID
import sqlite3

from application.ports.output.lead_repository_port import LeadRepositoryPort
from domain.entities.lead import Lead

class RawSqlLeadRepository(LeadRepositoryPort):
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def save(self, lead: Lead) -> Lead:
        custom_attrs_json = json.dumps(lead.custom_attributes)
        assigned_agent_str = str(lead.assigned_agent_id) if lead.assigned_agent_id else None

        sql = """
        INSERT OR REPLACE INTO leads (
            id, tenant_id, first_name, last_name, email, company, budget, industry,
            custom_attributes, phone, score, status, assigned_agent_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        self.connection.execute(
            sql,
            (
                str(lead.id),
                str(lead.tenant_id),
                lead.first_name,
                lead.last_name,
                str(lead.email),
                lead.company,
                float(lead.budget),
                lead.industry,
                custom_attrs_json,
                lead.phone,
                int(lead.score),
                lead.status.value,
                assigned_agent_str,
                lead.created_at.isoformat(),
            ),
        )
        return lead

    def _row_to_lead(self, row) -> Lead:
        custom_attrs = json.loads(row["custom_attributes"]) if row["custom_attributes"] else {}
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
        cursor = self.connection.execute("SELECT * FROM leads WHERE id = ?", (str(lead_id),))
        row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_lead(row)

    def list_by_tenant(self, tenant_id: UUID, limit: int = 100, offset: int = 0) -> List[Lead]:
        cursor = self.connection.execute(
            "SELECT * FROM leads WHERE tenant_id = ? LIMIT ? OFFSET ?",
            (str(tenant_id), limit, offset),
        )
        rows = cursor.fetchall()
        return [self._row_to_lead(row) for row in rows]
