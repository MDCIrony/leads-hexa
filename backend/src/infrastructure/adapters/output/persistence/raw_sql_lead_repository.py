from typing import Dict, List, Optional
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from application.ports.output.lead_repository_port import LeadRepositoryPort
from domain.entities.lead import Lead
from domain.value_objects.enums import LeadStatus
from domain.value_objects.score_breakdown import AppliedRule


class RawSqlLeadRepository(LeadRepositoryPort):
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def save(self, lead: Lead) -> Lead:
        assigned_agent_id = lead.assigned_agent_id.value if lead.assigned_agent_id else None
        breakdown = Jsonb(
            [
                {"rule_id": str(a.rule_id), "name": a.name, "score_delta": a.score_delta}
                for a in lead.score_breakdown
            ]
        )

        sql = """
        INSERT INTO leads (
            id, tenant_id, source_id, first_name, last_name, email, company, budget, industry,
            custom_attributes, phone, score, status, assigned_agent_id, created_at,
            assigned_at, discard_reason, disqualification_reason, updated_at, score_breakdown
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            tenant_id = EXCLUDED.tenant_id,
            source_id = EXCLUDED.source_id,
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
            created_at = EXCLUDED.created_at,
            assigned_at = EXCLUDED.assigned_at,
            discard_reason = EXCLUDED.discard_reason,
            disqualification_reason = EXCLUDED.disqualification_reason,
            updated_at = EXCLUDED.updated_at,
            score_breakdown = EXCLUDED.score_breakdown
        """
        self.connection.execute(
            sql,
            (
                lead.id.value,
                lead.tenant_id.value,
                lead.source_id.value,
                lead.first_name,
                lead.last_name,
                str(lead.email) if lead.email else None,
                lead.company,
                float(lead.budget),
                lead.industry,
                Jsonb(lead.custom_attributes),
                lead.phone,
                int(lead.score),
                lead.status.value,
                assigned_agent_id,
                lead.created_at,
                lead.assigned_at,
                lead.discard_reason,
                lead.disqualification_reason,
                lead.updated_at,
                breakdown,
            ),
        )
        return lead

    def _row_to_lead(self, row) -> Lead:
        custom_attrs = row["custom_attributes"]
        return Lead.create(
            lead_id=row["id"],
            tenant_id=row["tenant_id"],
            source_id=row["source_id"],
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
            assigned_at=row["assigned_at"],
            discard_reason=row["discard_reason"],
            disqualification_reason=row["disqualification_reason"],
            updated_at=row["updated_at"],
            score_breakdown=[
                AppliedRule(
                    rule_id=UUID(entry["rule_id"]),
                    name=entry["name"],
                    score_delta=entry["score_delta"],
                )
                for entry in (row["score_breakdown"] or [])
            ],
        )

    def get_by_id(self, lead_id: UUID) -> Optional[Lead]:
        cursor = self.connection.execute("SELECT * FROM leads WHERE id = %s", (lead_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_lead(row)

    def get_by_id_and_tenant(self, lead_id: UUID, tenant_id: UUID) -> Optional[Lead]:
        row = self.connection.execute(
            "SELECT * FROM leads WHERE id = %s AND tenant_id = %s", (lead_id, tenant_id)
        ).fetchone()
        return self._row_to_lead(row) if row else None

    def list_by_tenant(self, tenant_id: UUID, limit: int = 100, offset: int = 0) -> List[Lead]:
        cursor = self.connection.execute(
            "SELECT * FROM leads WHERE tenant_id = %s ORDER BY created_at DESC, id LIMIT %s OFFSET %s",
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

    def count_by_source(self, tenant_id: UUID, source_id: UUID) -> int:
        cursor = self.connection.execute(
            "SELECT COUNT(*) AS total FROM leads WHERE tenant_id = %s AND source_id = %s",
            (tenant_id, source_id),
        )
        row = cursor.fetchone()
        return int(row["total"]) if row else 0

    def list_by_agent(
        self, tenant_id: UUID, agent_id: UUID, limit: int = 100, offset: int = 0
    ) -> List[Lead]:
        rows = self.connection.execute(
            """
            SELECT * FROM leads
            WHERE tenant_id = %s AND assigned_agent_id = %s
            ORDER BY created_at DESC, id LIMIT %s OFFSET %s
            """,
            (tenant_id, agent_id, limit, offset),
        ).fetchall()
        return [self._row_to_lead(row) for row in rows]

    def count_by_agent(self, tenant_id: UUID, agent_id: UUID) -> int:
        row = self.connection.execute(
            "SELECT COUNT(*) AS count FROM leads WHERE tenant_id = %s AND assigned_agent_id = %s",
            (tenant_id, agent_id),
        ).fetchone()
        return int(row["count"])

    def active_load_by_agent(self, tenant_id: UUID) -> Dict[UUID, int]:
        """Return how many active leads each agent of this organization holds.

        Derived on read rather than kept in a counter column: a counter that
        is only ever incremented drifts from reality on the first lead that
        gets discarded or reassigned."""
        rows = self.connection.execute(
            """
            SELECT assigned_agent_id, COUNT(*) AS load
            FROM leads
            WHERE tenant_id = %s
              AND assigned_agent_id IS NOT NULL
              AND status = %s
            GROUP BY assigned_agent_id
            """,
            (tenant_id, LeadStatus.ASSIGNED.value),
        ).fetchall()
        return {row["assigned_agent_id"]: int(row["load"]) for row in rows}
