from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from uuid import UUID

from domain.records.intake_record import IntakeRecord


@dataclass(frozen=True)
class GetIntakeRecordsQuery:
    tenant_id: UUID
    status: Optional[str] = None
    job_id: Optional[UUID] = None
    limit: int = 100
    offset: int = 0


@dataclass(frozen=True)
class IntakeRecordsPageResult:
    items: List[IntakeRecord]
    total: int


@dataclass(frozen=True)
class PromoteIntakeRecordCommand:
    tenant_id: UUID
    record_id: UUID
    # The whole corrected payload, not a patch: the manager resends the form.
    payload: Dict[str, Any]


@dataclass(frozen=True)
class LeadProcessedResult:
    lead_id: str
    status: str
    score: int
    assigned_agent_id: Optional[str] = None
    applied_rules_count: int = 0
    error: Optional[str] = None
    error_code: Optional[str] = None
    # Always set, admitted or rejected: the link back to the payload that produced it.
    intake_record_id: str = ""


@dataclass(frozen=True)
class IntakeStatsResult:
    pending: int
    rejected: int
    pending_intake: int
