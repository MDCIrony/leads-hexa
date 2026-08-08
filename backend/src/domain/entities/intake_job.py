from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from domain.exceptions import DomainException
from domain.value_objects.enums import IntakeJobKind, IntakeJobStatus
from domain.value_objects.intake_job_id import IntakeJobId
from domain.value_objects.lead_source_id import LeadSourceId
from domain.value_objects.tenant_id import TenantId

# Both terminal: no method accepts either as a starting state.
_TERMINAL = (IntakeJobStatus.COMPLETED, IntakeJobStatus.FAILED)


@dataclass
class IntakeJob:
    """One ingestion operation (a single lead or a whole file) and its progress."""

    id: IntakeJobId
    tenant_id: TenantId
    source_id: LeadSourceId
    kind: IntakeJobKind
    status: IntakeJobStatus = IntakeJobStatus.PENDING
    total_items: Optional[int] = None
    succeeded: int = 0
    failed: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

    @staticmethod
    def create(
        tenant_id: UUID,
        source_id: UUID,
        kind: IntakeJobKind,
        total_items: Optional[int] = None,
    ) -> "IntakeJob":
        """Factory method that encapsulates Value Object construction."""
        return IntakeJob(
            id=IntakeJobId(),
            tenant_id=tenant_id if isinstance(tenant_id, TenantId) else TenantId(tenant_id),
            source_id=source_id if isinstance(source_id, LeadSourceId) else LeadSourceId(source_id),
            kind=kind if isinstance(kind, IntakeJobKind) else IntakeJobKind(kind),
            total_items=total_items,
        )

    def start(self) -> None:
        if self.status != IntakeJobStatus.PENDING:
            raise DomainException(
                f"Cannot start an intake job from status {self.status.value}",
                error_code="INVALID_JOB_TRANSITION",
            )
        self.status = IntakeJobStatus.PROCESSING

    def set_total(self, total: int) -> None:
        # PENDING is accepted too: a batch job materialises its records (and
        # so learns its total) in the transaction right after reception,
        # before ProcessIntakeJobUseCase ever calls start(). Still only once,
        # and never once the job is terminal.
        if self.status not in (IntakeJobStatus.PENDING, IntakeJobStatus.PROCESSING) or self.total_items is not None:
            raise DomainException(
                "Cannot set the total for this intake job",
                error_code="INVALID_JOB_TRANSITION",
            )
        self.total_items = total

    def record_success(self) -> None:
        self.succeeded += 1

    def record_failure(self) -> None:
        self.failed += 1

    def complete(self) -> None:
        if self.status in _TERMINAL:
            raise DomainException(
                f"Cannot complete an intake job from status {self.status.value}",
                error_code="INVALID_JOB_TRANSITION",
            )
        self.status = IntakeJobStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)

    def fail(self) -> None:
        if self.status in _TERMINAL:
            raise DomainException(
                f"Cannot fail an intake job from status {self.status.value}",
                error_code="INVALID_JOB_TRANSITION",
            )
        self.status = IntakeJobStatus.FAILED
        self.completed_at = datetime.now(timezone.utc)

    def reset_counters(self) -> None:
        # Accepted from PENDING too: a job that never made it past PENDING is
        # still safe to relaunch, and this keeps that case from needing a
        # special branch in the caller.
        if self.status in _TERMINAL:
            raise DomainException(
                f"Cannot reprocess an intake job from status {self.status.value}",
                error_code="INVALID_JOB_TRANSITION",
            )
        self.succeeded = 0
        self.failed = 0
        self.status = IntakeJobStatus.PENDING
