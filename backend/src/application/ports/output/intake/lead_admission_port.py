from abc import ABC, abstractmethod

from application.dtos.admissions import AdmissionRequest, AdmissionResult


class AdmissionUnavailable(Exception):
    """The decision could not be had right now; the record stays PENDING and is retried."""


class LeadAdmissionPort(ABC):
    """Intake's way to lead-core's decision: in process before the cut, over HTTP after it."""

    @abstractmethod
    def admit(self, request: AdmissionRequest) -> AdmissionResult:
        """Idempotent by (tenant_id, intake_record_id). Raises AdmissionUnavailable."""
