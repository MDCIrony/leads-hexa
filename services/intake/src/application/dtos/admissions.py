"""Intake's own copy of the admission contract; the JSON schema under contracts/ is the shared truth."""
from dataclasses import dataclass
from typing import Optional
from uuid import UUID


@dataclass(frozen=True)
class AdmissionCandidate:
    """Every scalar travels as text, budget included: lead-core owns the validation."""

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
