from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import psycopg

from domain.value_objects.enums import LeadStatus


class LeadStatistics:
    """The aggregate reads for the panel, mixed into RawSqlLeadRepository."""

    connection: psycopg.Connection

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
