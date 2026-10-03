from abc import ABC, abstractmethod
from typing import List
from uuid import UUID

from application.dtos.admissions import AdmissionLookupItem, AdmissionRequest, AdmissionResult


class AdmitLeadInputPort(ABC):
    @abstractmethod
    def execute(self, request: AdmissionRequest) -> AdmissionResult:
        pass


class LookupAdmissionsInputPort(ABC):
    @abstractmethod
    def execute(self, intake_record_ids: List[UUID]) -> List[AdmissionLookupItem]:
        pass
