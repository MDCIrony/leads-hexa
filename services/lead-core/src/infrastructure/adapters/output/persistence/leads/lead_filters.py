from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from domain.value_objects.enums import LeadStatus


class LeadFilters:
    """The optional list filters, mixed into RawSqlLeadRepository."""

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
