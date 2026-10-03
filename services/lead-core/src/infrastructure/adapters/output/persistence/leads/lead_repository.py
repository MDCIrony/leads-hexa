from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

import psycopg

from application.ports.output.leads.lead_repository_port import LeadRepositoryPort
from domain.leads.lead import Lead
from domain.value_objects.enums import LeadStatus
from infrastructure.adapters.output.persistence.leads.admission_lookups import LeadAdmissionLookups
from infrastructure.adapters.output.persistence.leads.lead_filters import LeadFilters
from infrastructure.adapters.output.persistence.leads.lead_rows import row_to_lead, save_lead
from infrastructure.adapters.output.persistence.leads.lead_statistics import LeadStatistics


class RawSqlLeadRepository(LeadFilters, LeadStatistics, LeadAdmissionLookups, LeadRepositoryPort):
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def save(self, lead: Lead) -> Lead:
        return save_lead(self.connection, lead)

    def get_by_id(self, lead_id: UUID) -> Optional[Lead]:
        cursor = self.connection.execute("SELECT * FROM leads WHERE id = %s", (lead_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return row_to_lead(row)

    def get_by_id_and_tenant(self, lead_id: UUID, tenant_id: UUID) -> Optional[Lead]:
        row = self.connection.execute(
            "SELECT * FROM leads WHERE id = %s AND tenant_id = %s", (lead_id, tenant_id)
        ).fetchone()
        return row_to_lead(row) if row else None

    def list_by_tenant(
        self,
        tenant_id: UUID,
        status: Optional[LeadStatus] = None,
        assigned_agent_id: Optional[UUID] = None,
        group_id: Optional[UUID] = None,
        source_id: Optional[UUID] = None,
        search: Optional[str] = None,
        updated_since: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Lead]:
        clauses, params = self._filters(
            tenant_id, status, assigned_agent_id, group_id, source_id, search, updated_since
        )
        query = "SELECT * FROM leads WHERE tenant_id = %s"
        query_params: List[Any] = [tenant_id]
        for clause in clauses:
            query += f" AND {clause}"
        query_params += params
        # Ordered by the very field being filtered when catching up: paging by
        # creation date while filtering by update time skips rows that get
        # touched between one page and the next, which is exactly the lead the
        # consumer was asking about.
        if updated_since is not None:
            query += " ORDER BY updated_at, id LIMIT %s OFFSET %s"
        else:
            query += " ORDER BY created_at DESC, id LIMIT %s OFFSET %s"
        query_params += [limit, offset]
        rows = self.connection.execute(query, query_params).fetchall()
        return [row_to_lead(row) for row in rows]

    def count_by_tenant(
        self,
        tenant_id: UUID,
        status: Optional[LeadStatus] = None,
        assigned_agent_id: Optional[UUID] = None,
        group_id: Optional[UUID] = None,
        source_id: Optional[UUID] = None,
        search: Optional[str] = None,
        updated_since: Optional[datetime] = None,
    ) -> int:
        clauses, params = self._filters(
            tenant_id, status, assigned_agent_id, group_id, source_id, search, updated_since
        )
        query = "SELECT COUNT(*) AS count FROM leads WHERE tenant_id = %s"
        query_params: List[Any] = [tenant_id]
        for clause in clauses:
            query += f" AND {clause}"
        query_params += params
        row = self.connection.execute(query, query_params).fetchone()
        return int(row["count"]) if row else 0

    def list_by_agent(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        status: Optional[LeadStatus] = None,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Lead]:
        clauses, params = self._filters(tenant_id, status, None, None, None, search)
        query = "SELECT * FROM leads WHERE tenant_id = %s AND assigned_agent_id = %s"
        query_params: List[Any] = [tenant_id, agent_id]
        for clause in clauses:
            query += f" AND {clause}"
        query_params += params
        query += " ORDER BY assigned_at DESC NULLS LAST, id LIMIT %s OFFSET %s"
        query_params += [limit, offset]
        rows = self.connection.execute(query, query_params).fetchall()
        return [row_to_lead(row) for row in rows]

    def count_by_agent(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        status: Optional[LeadStatus] = None,
        search: Optional[str] = None,
    ) -> int:
        clauses, params = self._filters(tenant_id, status, None, None, None, search)
        query = "SELECT COUNT(*) AS count FROM leads WHERE tenant_id = %s AND assigned_agent_id = %s"
        query_params: List[Any] = [tenant_id, agent_id]
        for clause in clauses:
            query += f" AND {clause}"
        query_params += params
        row = self.connection.execute(query, query_params).fetchone()
        return int(row["count"])
