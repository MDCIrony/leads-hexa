"""The admission contract (contracts/schemas/lead-core/admission-*.v1) as the application sees it."""
from dataclasses import dataclass
from typing import Optional
from uuid import UUID


@dataclass(frozen=True)
class AdmissionCandidate:
    """Text, never numbers: `budget` is decimal text so no float rounds it on
    the way, and validating it is lead-core's job."""

    first_name: Optional[str]
    last_name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    company: Optional[str]
    industry: Optional[str]
    budget: Optional[str]
    custom_attributes: dict


@dataclass(frozen=True)
class AdmissionRequest:
    tenant_id: UUID
    intake_record_id: UUID
    source_id: UUID
    candidate: AdmissionCandidate


@dataclass(frozen=True)
class AdmissionError:
    field: str
    message: str
    error_code: Optional[str]


@dataclass(frozen=True)
class AdmissionResult:
    outcome: str  # "ADMITTED" | "REJECTED"
    lead_id: Optional[str] = None
    status: Optional[str] = None
    score: int = 0
    assigned_agent_id: Optional[str] = None
    applied_rules_count: int = 0
    errors: tuple[AdmissionError, ...] = ()


@dataclass(frozen=True)
class AdmissionLookupItem:
    intake_record_id: str
    tenant_id: str
    lead_id: str
