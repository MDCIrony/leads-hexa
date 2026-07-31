import json
from typing import List, Optional
from uuid import UUID
from application.ports.output.lead_repository_port import LeadRepositoryPort
from domain.entities.lead import Lead
from domain.value_objects import (
    LeadId,
    TenantId,
    AgentId,
    EmailAddress,
    Money,
    Score,
    LeadStatus,
)
from infrastructure.adapters.output.persistence.connection import RawSqlDatabase

class RawSqlLeadRepository(LeadRepositoryPort):
    def __init__(self, db: RawSqlDatabase) -> None:
        self.db = db

    def save(self, lead: Lead) -> Lead:
        conn = self.db.get_connection()
        custom_attrs_json = json.dumps(lead.custom_attributes)
        assigned_agent_str = str(lead.assigned_agent_id) if lead.assigned_agent_id else None

        sql = """
        INSERT OR REPLACE INTO leads (
            id, tenant_id, first_name, last_name, email, company, budget, industry,
            custom_attributes, phone, score, status, assigned_agent_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with conn:
            conn.execute(
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

    def get_by_id(self, lead_id: UUID) -> Optional[Lead]:
        conn = self.db.get_connection()
        cursor = conn.execute("SELECT * FROM leads WHERE id = ?", (str(lead_id),))
        row = cursor.fetchone()
        if not row:
            return None

        custom_attrs = json.loads(row["custom_attributes"]) if row["custom_attributes"] else {}
        assigned_agent = AgentId(row["assigned_agent_id"]) if row["assigned_agent_id"] else None

        return Lead(
            id=LeadId(row["id"]),
            tenant_id=TenantId(row["tenant_id"]),
            first_name=row["first_name"],
            last_name=row["last_name"],
            email=EmailAddress(row["email"]),
            company=row["company"],
            budget=Money(row["budget"]),
            industry=row["industry"],
            custom_attributes=custom_attrs,
            phone=row["phone"],
            score=Score(row["score"]),
            status=LeadStatus(row["status"]),
            assigned_agent_id=assigned_agent,
        )

    def list_by_tenant(self, tenant_id: UUID, limit: int = 100, offset: int = 0) -> List[Lead]:
        conn = self.db.get_connection()
        cursor = conn.execute(
            "SELECT * FROM leads WHERE tenant_id = ? LIMIT ? OFFSET ?",
            (str(tenant_id), limit, offset),
        )
        rows = cursor.fetchall()
        result = []
        for row in rows:
            custom_attrs = json.loads(row["custom_attributes"]) if row["custom_attributes"] else {}
            assigned_agent = AgentId(row["assigned_agent_id"]) if row["assigned_agent_id"] else None
            result.append(
                Lead(
                    id=LeadId(row["id"]),
                    tenant_id=TenantId(row["tenant_id"]),
                    first_name=row["first_name"],
                    last_name=row["last_name"],
                    email=EmailAddress(row["email"]),
                    company=row["company"],
                    budget=Money(row["budget"]),
                    industry=row["industry"],
                    custom_attributes=custom_attrs,
                    phone=row["phone"],
                    score=Score(row["score"]),
                    status=LeadStatus(row["status"]),
                    assigned_agent_id=assigned_agent,
                )
            )
        return result
