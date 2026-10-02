from dataclasses import asdict
from typing import Any

from application.dtos.admissions import AdmissionError, AdmissionRequest, AdmissionResult
from application.ports.output.admissions import LeadAdmissionPort
from infrastructure.adapters.output.admissions.fields import integer, text, uuid_text
from infrastructure.adapters.output.admissions.lead_core_client import LeadCoreClient, unavailable


def _error(item: Any) -> AdmissionError:
    code = item.get("error_code")
    return AdmissionError(text(item["field"]), text(item["message"]), None if code is None else text(code))


def _result(body: Any) -> AdmissionResult:
    """Anything short of a complete decision raises, which the caller reads as invalid."""
    outcome = body["outcome"]
    if outcome == "ADMITTED":
        agent = body["assigned_agent_id"]
        return AdmissionResult(
            outcome=outcome,
            lead_id=uuid_text(body["lead_id"]),
            # Opaque: lead-core owns the lead statuses, and intake only relays them.
            status=text(body["status"]),
            score=integer(body["score"]),
            assigned_agent_id=None if agent is None else uuid_text(agent),
            applied_rules_count=integer(body["applied_rules_count"]),
        )
    if outcome == "REJECTED":
        errors = body["errors"]
        if not isinstance(errors, list) or not errors:
            raise ValueError("a rejection without errors")
        return AdmissionResult(outcome=outcome, errors=tuple(_error(e) for e in errors))
    raise ValueError("unknown outcome")


class HttpLeadAdmission(LeadAdmissionPort):
    """`POST /internal/v1/admissions` (contracts/schemas/lead-core/admission-*.v1)."""

    def __init__(self, lead_core: LeadCoreClient) -> None:
        self._lead_core = lead_core

    def admit(self, request: AdmissionRequest) -> AdmissionResult:
        response = self._lead_core.send("POST", json={
            "tenant_id": str(request.tenant_id),
            "intake_record_id": str(request.intake_record_id),
            "source_id": str(request.source_id),
            "candidate": asdict(request.candidate),
        })
        try:
            return _result(response.json())
        except (ValueError, KeyError, TypeError, AttributeError):
            raise unavailable("malformed admission body") from None
