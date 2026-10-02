"""A scripted stand-in for lead-core: the decision is not intake's, so tests only choose its answer."""
from typing import Callable, Optional
from uuid import uuid4

from application.dtos.admissions import AdmissionError, AdmissionRequest, AdmissionResult
from application.ports.output.admissions import AdmissionUnavailable, LeadAdmissionPort
from tests.unit.application.doubles.uow import InMemoryUnitOfWork


def admitted(lead_id: Optional[str] = None, **fields) -> AdmissionResult:
    return AdmissionResult(outcome="ADMITTED", lead_id=lead_id or str(uuid4()), status="QUALIFIED", **fields)


def rejected(field: str = "email", message: str = "bad email", code: Optional[str] = "INVALID_EMAIL") -> AdmissionResult:
    return AdmissionResult(outcome="REJECTED", errors=(AdmissionError(field, message, code),))


class FakeLeadAdmission(LeadAdmissionPort):
    """Remembers every request and the transactions open at the moment of each call.

    Admits by default, like a lead-core with no rules; `rule` overrides the answer
    per request and may raise AdmissionUnavailable."""

    def __init__(
        self, uow: Optional[InMemoryUnitOfWork] = None,
        rule: Optional[Callable[[AdmissionRequest], AdmissionResult]] = None,
    ) -> None:
        self.uow, self.rule = uow, rule
        self.requests: list[AdmissionRequest] = []
        self.open_transactions_at_call: list[int] = []

    def admit(self, request: AdmissionRequest) -> AdmissionResult:
        self.requests.append(request)
        self.open_transactions_at_call.append(self.uow.open_transactions if self.uow else 0)
        return self.rule(request) if self.rule else admitted()


def unavailable(_: AdmissionRequest) -> AdmissionResult:
    raise AdmissionUnavailable("lead-core is down")
