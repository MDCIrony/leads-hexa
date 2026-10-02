import math
from decimal import Decimal
from typing import Any, Dict, Optional

from application.dtos.admissions import AdmissionCandidate
from application.dtos.reception import IngestLeadCommand
from domain.records.intake_record import IntakeRecord


def payload_of(command: IngestLeadCommand) -> Dict[str, Any]:
    """Snapshot of the raw command as a JSONB-serializable dict.

    Never raises on a malformed value: it runs before anyone has judged the
    data, so it cannot reject what lead-core is about to."""
    budget = command.budget
    if isinstance(budget, Decimal):
        budget = float(budget)
    # NaN and ±Infinity are the values json.dumps turns into bare tokens
    # Postgres refuses as JSONB, which would fail the insert of a whole batch
    # over one bad cell. The record must persist even when its budget is
    # unusable; lead-core rejects it later with the field named.
    if isinstance(budget, float) and not math.isfinite(budget):
        budget = None
    return {
        "tenant_id": str(command.tenant_id),
        "source_id": str(command.source_id),
        "first_name": command.first_name,
        "last_name": command.last_name,
        "company": command.company,
        "budget": budget,
        "industry": command.industry,
        "custom_attributes": command.custom_attributes,
        "phone": command.phone,
        "email": command.email,
    }


def command_from_record(record: IntakeRecord) -> IngestLeadCommand:
    """Rebuild the command from what was stored, without validating it.

    tenant_id and source_id come from the record, never from the payload: the
    organization was authenticated at reception, and the payload is untrusted
    input that merely carries a copy of both."""
    payload = record.payload or {}
    return IngestLeadCommand(
        tenant_id=record.tenant_id.value,
        source_id=record.source_id.value,
        first_name=payload.get("first_name"),
        last_name=payload.get("last_name"),
        company=payload.get("company"),
        budget=payload.get("budget"),
        industry=payload.get("industry"),
        custom_attributes=payload.get("custom_attributes") or {},
        phone=payload.get("phone"),
        email=payload.get("email"),
    )


def _text(value: Any) -> Optional[str]:
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, float):
        # repr, not str: the shortest text that round-trips, so 0.1 stays "0.1"
        # instead of exposing the binary expansion a direct Decimal(float) would.
        return str(Decimal(repr(value)))
    return str(value)


def candidate_of(command: IngestLeadCommand) -> AdmissionCandidate:
    """The contract carries every scalar as text; a historical payload may hold numbers."""
    return AdmissionCandidate(
        first_name=_text(command.first_name),
        last_name=_text(command.last_name),
        email=_text(command.email),
        phone=_text(command.phone),
        company=_text(command.company),
        industry=_text(command.industry),
        budget=_text(command.budget),
        custom_attributes=command.custom_attributes or {},
    )
