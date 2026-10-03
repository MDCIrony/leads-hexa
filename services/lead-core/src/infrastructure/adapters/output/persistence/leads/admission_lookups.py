from typing import List, Optional
from uuid import UUID

import psycopg

from application.dtos.admissions import AdmissionLookupItem
from domain.leads.lead import Lead
from infrastructure.adapters.output.persistence.leads.lead_rows import row_to_lead


class LeadAdmissionLookups:
    """The reads keyed by intake record, mixed into RawSqlLeadRepository."""

    connection: psycopg.Connection

    def get_by_intake_record(self, tenant_id: UUID, intake_record_id: UUID) -> Optional[Lead]:
        row = self.connection.execute(
            "SELECT * FROM leads WHERE tenant_id = %s AND intake_record_id = %s", (tenant_id, intake_record_id)
        ).fetchone()
        return row_to_lead(row) if row else None

    def list_by_intake_records(self, intake_record_ids: List[UUID]) -> List[AdmissionLookupItem]:
        rows = self.connection.execute(
            "SELECT intake_record_id, tenant_id, id FROM leads WHERE intake_record_id = ANY(%s)"
            " ORDER BY intake_record_id",
            (list(intake_record_ids),),
        ).fetchall()
        return [AdmissionLookupItem(str(row["intake_record_id"]), str(row["tenant_id"]), str(row["id"]))
                for row in rows]
