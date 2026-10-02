"""How an ingestion command is stored on its intake record, and how it travels to lead-core."""
import math
from decimal import Decimal
from typing import Any, Dict, Optional

from application.dtos.admissions import AdmissionCandidate
from application.dtos.commands import IngestLeadCommand
from domain.entities.intake_record import IntakeRecord


def payload_of(command: IngestLeadCommand) -> Dict[str, Any]:
    """Snapshot the raw command into a JSONB-serializable dict.

    Must not raise on a malformed value (e.g. a non-numeric budget): this
    runs before Lead.create, so it cannot re-run the validation that is
    about to happen and reject something the domain hasn't judged yet."""
    budget = command.budget
    if isinstance(budget, Decimal):
        budget = float(budget)
    # NaN and ±Infinity are the two values json.dumps turns into bare tokens
    # Postgres refuses as JSONB, which would fail the insert of a whole batch
    # over one bad cell. The record must persist even when its budget is
    # unusable; the domain rejects it on the next phase, with the field named.
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
    """Rebuild the command from what was stored, without re-validating it.

    tenant_id and source_id come from the record, never from the payload: the
    organization is the one that was authenticated at reception (C4), and the
    payload is untrusted input that happens to carry a copy of both."""
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


def candidate_of(command: IngestLeadCommand) -> AdmissionCandidate:
    """The command as admission-request.v1 carries it: every scalar as text."""
    return AdmissionCandidate(
        first_name=_text(command.first_name), last_name=_text(command.last_name), email=_text(command.email),
        phone=_text(command.phone), company=_text(command.company), industry=_text(command.industry),
        budget=_text(command.budget), custom_attributes=command.custom_attributes or {},
    )


def _text(value: Any) -> Optional[str]:
    if value is None or isinstance(value, str):
        return value
    # Through repr, not str(Decimal(x)): Decimal(0.1) spells out the binary
    # float in full, while repr is the shortest text that reads back as it.
    if isinstance(value, float):
        return str(Decimal(repr(value)))
    return str(value)
