from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID

from application.dtos.admissions import AdmissionRequest, AdmissionResult


class AdmissionUnavailable(Exception):
    """lead-core gave no usable answer: a transport failure, a timeout, a non-200 or an invalid body.

    Transient by definition. The record stays PENDING so a later run asks again."""


class LeadAdmissionPort(ABC):
    @abstractmethod
    def admit(self, request: AdmissionRequest) -> AdmissionResult:
        """Idempotent per (tenant_id, intake_record_id); raises AdmissionUnavailable when it cannot answer."""


@dataclass(frozen=True)
class AdmissionLookupItem:
    intake_record_id: str
    tenant_id: str
    lead_id: str


class AdmissionLookupPort(ABC):
    @abstractmethod
    def lookup(self, intake_record_ids: list[UUID]) -> list[AdmissionLookupItem]:
        """The admissions lead-core holds for these records; unknown ids are absent."""
