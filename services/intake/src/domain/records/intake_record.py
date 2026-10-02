from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from domain.exceptions import DomainException
from domain.value_objects.enums import IntakeRecordStatus
from domain.value_objects.intake_job_id import IntakeJobId
from domain.value_objects.intake_record_id import IntakeRecordId
from domain.value_objects.lead_id import LeadId
from domain.value_objects.lead_source_id import LeadSourceId
from domain.value_objects.tenant_id import TenantId

# Both terminal: neither PROMOTED nor DISCARDED can be reopened by any method.
_REOPENABLE_STATUSES = (IntakeRecordStatus.PENDING, IntakeRecordStatus.REJECTED)


@dataclass(frozen=True)
class IntakeError:
    """Why one field of a payload could not be interpreted.

    Per-field rather than one message per record: a manager fixing a CSV column
    mapping needs to know which column, not that "the row failed"."""

    field: str
    message: str
    received_value: Optional[str] = None
    error_code: Optional[str] = None


@dataclass
class IntakeRecord:
    id: IntakeRecordId
    tenant_id: TenantId
    source_id: LeadSourceId
    payload: Dict[str, Any]
    status: IntakeRecordStatus = IntakeRecordStatus.PENDING
    errors: List[IntakeError] = field(default_factory=list)
    lead_id: Optional[LeadId] = None
    job_id: Optional[IntakeJobId] = None
    # A bare default would freeze at class-definition time.
    received_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    processed_at: Optional[datetime] = None

    @classmethod
    def create(
        cls,
        tenant_id: Union[str, UUID, TenantId],
        source_id: Union[str, UUID, LeadSourceId],
        payload: Dict[str, Any],
        record_id: Optional[Union[str, UUID, IntakeRecordId]] = None,
        status: Union[str, IntakeRecordStatus] = IntakeRecordStatus.PENDING,
        errors: Optional[List[IntakeError]] = None,
        lead_id: Optional[Union[str, UUID, LeadId]] = None,
        received_at: Optional[datetime] = None,
        processed_at: Optional[datetime] = None,
        job_id: Optional[Union[str, UUID, IntakeJobId]] = None,
    ) -> "IntakeRecord":
        """Factory method that encapsulates Value Object construction."""
        return cls(
            id=record_id if isinstance(record_id, IntakeRecordId) else IntakeRecordId(record_id),
            tenant_id=tenant_id if isinstance(tenant_id, TenantId) else TenantId(tenant_id),
            source_id=source_id if isinstance(source_id, LeadSourceId) else LeadSourceId(source_id),
            payload=payload,
            status=status if isinstance(status, IntakeRecordStatus) else IntakeRecordStatus(status),
            errors=list(errors) if errors else [],
            lead_id=lead_id if (lead_id is None or isinstance(lead_id, LeadId)) else LeadId(lead_id),
            received_at=received_at or datetime.now(timezone.utc),
            processed_at=processed_at,
            job_id=job_id if (job_id is None or isinstance(job_id, IntakeJobId)) else IntakeJobId(job_id),
        )

    def promote(self, lead_id: Union[str, UUID, LeadId]) -> None:
        # REJECTED is an allowed source on purpose: a manager fixes what failed
        # and promotes the corrected record instead of re-submitting it.
        if self.status not in _REOPENABLE_STATUSES:
            raise DomainException(
                f"Cannot promote an intake record from status {self.status.value}",
                error_code="INVALID_INTAKE_TRANSITION",
            )
        self.lead_id = lead_id if isinstance(lead_id, LeadId) else LeadId(lead_id)
        self.status = IntakeRecordStatus.PROMOTED
        self.processed_at = datetime.now(timezone.utc)

    def reject(self, errors: List[IntakeError]) -> None:
        # Same reason as promote(): the manager corrects a rejected record and
        # the correction can fail again. Both transitions start from the same
        # states, or the inbox would never close the loop.
        if self.status not in _REOPENABLE_STATUSES:
            raise DomainException(
                f"Cannot reject an intake record from status {self.status.value}",
                error_code="INVALID_INTAKE_TRANSITION",
            )
        if not errors:
            raise DomainException(
                "Rejecting an intake record requires at least one error",
                error_code="REJECTION_WITHOUT_ERRORS",
            )
        self.errors = list(errors)
        self.status = IntakeRecordStatus.REJECTED
        self.processed_at = datetime.now(timezone.utc)

    def discard(self) -> None:
        if self.status not in _REOPENABLE_STATUSES:
            raise DomainException(
                f"Cannot discard an intake record from status {self.status.value}",
                error_code="INVALID_INTAKE_TRANSITION",
            )
        self.status = IntakeRecordStatus.DISCARDED
        self.processed_at = datetime.now(timezone.utc)
