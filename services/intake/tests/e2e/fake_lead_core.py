"""The only stand-in in the e2e stack: lead-core's decision, without a network.

It applies the two checks the scenarios need (email shape, a positive budget) and is
idempotent per (tenant, record) like the real endpoint, so a retried record cannot
mint a second lead."""
import re
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from application.dtos.admissions import AdmissionError, AdmissionRequest, AdmissionResult
from application.ports.output.admissions import AdmissionUnavailable, LeadAdmissionPort

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class FakeLeadCore(LeadAdmissionPort):
    def __init__(self) -> None:
        self.leads: dict[tuple, str] = {}
        self.down = False

    def admit(self, request: AdmissionRequest) -> AdmissionResult:
        if self.down:
            raise AdmissionUnavailable("lead-core is down")
        key = (request.tenant_id, request.intake_record_id)
        candidate = request.candidate
        if candidate.email is not None and not _EMAIL.match(candidate.email):
            return self._rejected("email", "Invalid email", "INVALID_EMAIL")
        try:
            budget_ok = candidate.budget is not None and Decimal(candidate.budget) > 0
        except InvalidOperation:
            budget_ok = False
        if not budget_ok:
            return self._rejected("budget", "Budget must be positive", "INVALID_BUDGET")
        lead_id = self.leads.setdefault(key, str(uuid4()))
        return AdmissionResult(outcome="ADMITTED", lead_id=lead_id, status="QUALIFIED", score=10)

    @staticmethod
    def _rejected(field: str, message: str, code: str) -> AdmissionResult:
        return AdmissionResult(outcome="REJECTED", errors=(AdmissionError(field, message, code),))
