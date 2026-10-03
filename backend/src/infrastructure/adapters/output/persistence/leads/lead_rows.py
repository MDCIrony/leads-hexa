"""A lead to and from its row in `leads`."""
import psycopg
from psycopg.types.json import Jsonb
from uuid import UUID

from application.ports.output.leads.lead_repository_port import DuplicateAdmission
from domain.leads.lead import Lead
from domain.value_objects.score_breakdown import AppliedRule

_ADMISSION_CONSTRAINT = "uq_leads_tenant_intake_record"

# intake_record_id is left out of the update: the link is set when the lead is
# admitted and nothing afterwards may move it to another record.
_UPSERT = """
INSERT INTO leads (
    id, tenant_id, source_id, first_name, last_name, email, company, budget, industry,
    custom_attributes, phone, score, status, assigned_agent_id, created_at,
    assigned_at, discard_reason, disqualification_reason, updated_at, score_breakdown, intake_record_id
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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


def save_lead(connection: psycopg.Connection, lead: Lead) -> Lead:
    params = (
        lead.id.value, lead.tenant_id.value, lead.source_id.value, lead.first_name, lead.last_name,
        str(lead.email) if lead.email else None, lead.company, float(lead.budget), lead.industry,
        Jsonb(lead.custom_attributes), lead.phone, int(lead.score), lead.status.value,
        lead.assigned_agent_id.value if lead.assigned_agent_id else None, lead.created_at,
        lead.assigned_at, lead.discard_reason, lead.disqualification_reason, lead.updated_at,
        Jsonb([applied.as_dict() for applied in lead.score_breakdown]), lead.intake_record_id,
    )
    try:
        connection.execute(_UPSERT, params)
    except psycopg.errors.UniqueViolation as error:
        # Only this constraint means "admitted twice"; any other keeps its type.
        if error.diag.constraint_name == _ADMISSION_CONSTRAINT:
            raise DuplicateAdmission(str(lead.intake_record_id)) from error
        raise
    return lead


def row_to_lead(row) -> Lead:
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
        custom_attributes=row["custom_attributes"],
        phone=row["phone"],
        score=row["score"],
        status=row["status"],
        assigned_agent_id=row["assigned_agent_id"],
        created_at=row["created_at"],
        assigned_at=row["assigned_at"],
        discard_reason=row["discard_reason"],
        disqualification_reason=row["disqualification_reason"],
        updated_at=row["updated_at"],
        intake_record_id=row["intake_record_id"],
        score_breakdown=[
            AppliedRule(rule_id=UUID(entry["rule_id"]), name=entry["name"], score_delta=entry["score_delta"])
            for entry in (row["score_breakdown"] or [])
        ],
    )
