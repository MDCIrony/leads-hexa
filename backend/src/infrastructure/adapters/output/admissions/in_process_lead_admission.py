from typing import Callable, Optional

from application.dtos.admissions import AdmissionRequest, AdmissionResult
from application.ports.output.intake.lead_admission_port import LeadAdmissionPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort
from application.use_cases.admissions.admit_lead import AdmitLeadUseCase
from domain.services.assignment_engine import AssignmentEngine


class InProcessLeadAdmission(LeadAdmissionPort):
    """The monolith's adapter until the cut: the same decision intake will
    reach over HTTP, in a unit of work of its own as it will have there."""

    def __init__(self, uow_factory: Callable[[], UnitOfWorkPort], engine: Optional[AssignmentEngine] = None) -> None:
        self._uow_factory = uow_factory
        self._engine = engine

    def admit(self, request: AdmissionRequest) -> AdmissionResult:
        return AdmitLeadUseCase(self._uow_factory(), self._engine).execute(request)
