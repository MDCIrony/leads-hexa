from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import psycopg

from application.ports.output.lead_repository_port import LeadRepositoryPort
from domain.entities.lead import Lead
from domain.value_objects.enums import LeadStatus
from infrastructure.adapters.output.persistence.leads.admission_lookups import LeadAdmissionLookups
from infrastructure.adapters.output.persistence.leads.lead_rows import row_to_lead, save_lead


class RawSqlLeadRepository(LeadAdmissionLookups, LeadRepositoryPort):
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

    def _filters(
        self,
        tenant_id: UUID,
        status: Optional[LeadStatus],
        assigned_agent_id: Optional[UUID],
        group_id: Optional[UUID],
        source_id: Optional[UUID],
        search: Optional[str],
        updated_since: Optional[datetime] = None,
    ) -> tuple[List[str], List[Any]]:
        # Built up rather than fully duplicated per filter combination: five
        # independent optional filters would otherwise mean many
        # near-identical query strings. Values still travel exclusively
        # through %s markers.
        clauses: List[str] = []
        params: List[Any] = []
        if updated_since is not None:
            clauses.append("updated_at >= %s")
            params.append(updated_since)
        if status is not None:
            clauses.append("status = %s")
            params.append(status.value)
        if assigned_agent_id is not None:
            clauses.append("assigned_agent_id = %s")
            params.append(assigned_agent_id)
        if group_id is not None:
            clauses.append(
                "assigned_agent_id IN (SELECT agent_id FROM advisors WHERE group_id = %s AND tenant_id = %s)"
            )
            params += [group_id, tenant_id]
        if source_id is not None:
            clauses.append("source_id = %s")
            params.append(source_id)
        if search:
            # ILIKE treats % and _ in the value itself as wildcards, not just
            # in the pattern we build: a literal "%" or "_" typed by the user
            # must be escaped, or "50%" would match "anything containing 50".
            escaped = self._escape_like(search)
            clauses.append(
                "(first_name ILIKE '%%' || %s || '%%' ESCAPE '\\'"
                " OR last_name ILIKE '%%' || %s || '%%' ESCAPE '\\'"
                " OR email ILIKE '%%' || %s || '%%' ESCAPE '\\'"
                " OR company ILIKE '%%' || %s || '%%' ESCAPE '\\')"
            )
            params += [escaped, escaped, escaped, escaped]
        return clauses, params

    @staticmethod
    def _escape_like(value: str) -> str:
        """Escape LIKE/ILIKE wildcards in a value that must be searched as
        literal text. Order matters: backslash first, so the backslashes it
        introduces for % and _ are not themselves re-escaped."""
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

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

    def count_by_source(self, tenant_id: UUID, source_id: UUID) -> int:
        cursor = self.connection.execute(
            "SELECT COUNT(*) AS total FROM leads WHERE tenant_id = %s AND source_id = %s",
            (tenant_id, source_id),
        )
        row = cursor.fetchone()
        return int(row["total"]) if row else 0

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

    def count_by_status(
        self,
        tenant_id: UUID,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, int]:
        query = "SELECT status, COUNT(*) AS count FROM leads WHERE tenant_id = %s"
        params: List[Any] = [tenant_id]
        if date_from is not None:
            query += " AND created_at >= %s"
            params.append(date_from)
        if date_to is not None:
            query += " AND created_at <= %s"
            params.append(date_to)
        query += " GROUP BY status"
        rows = self.connection.execute(query, params).fetchall()
        # Every LeadStatus starts at zero: the database only returns the
        # statuses that actually have leads, and the panel needs the complete set.
        result = {s.value: 0 for s in LeadStatus}
        for row in rows:
            result[row["status"]] = int(row["count"])
        return result

    def active_load_by_agent_with_names(self, tenant_id: UUID) -> List[Tuple[UUID, str, int]]:
        """Same load as active_load_by_agent, with each agent's name joined
        in for the panel to render without a second round trip."""
        rows = self.connection.execute(
            """
            SELECT l.assigned_agent_id, a.name, COUNT(*) AS load
            FROM leads l
            JOIN advisors a ON a.agent_id = l.assigned_agent_id
            WHERE l.tenant_id = %s
              AND l.assigned_agent_id IS NOT NULL
              AND l.status = %s
            GROUP BY l.assigned_agent_id, a.name
            ORDER BY load DESC, a.name
            """,
            (tenant_id, LeadStatus.ASSIGNED.value),
            # l.tenant_id already scopes the result, and a lead never points
            # to an agent outside its own organization, so a.tenant_id = %s
            # here would be redundant, not an extra safeguard.
        ).fetchall()
        return [(row["assigned_agent_id"], row["name"], int(row["load"])) for row in rows]
