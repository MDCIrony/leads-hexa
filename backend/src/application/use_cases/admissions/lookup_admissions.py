from typing import List
from uuid import UUID

from application.dtos.admissions import AdmissionLookupItem
from application.ports.input.admissions.admission_ports import LookupAdmissionsInputPort
from application.ports.output.unit_of_work_port import UnitOfWorkPort


class LookupAdmissionsUseCase(LookupAdmissionsInputPort):
    """Which intake records lead-core knows, and with which lead: intake's reconciliation asks."""

    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, intake_record_ids: List[UUID]) -> List[AdmissionLookupItem]:
        with self.uow:
            return self.uow.leads.list_by_intake_records(intake_record_ids)
