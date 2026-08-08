from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Union
from uuid import UUID

from domain.exceptions import DomainException
from domain.value_objects.agent_id import AgentId
from domain.value_objects.enums import NotificationKind
from domain.value_objects.intake_record_id import IntakeRecordId
from domain.value_objects.lead_id import LeadId
from domain.value_objects.notification_id import NotificationId
from domain.value_objects.tenant_id import TenantId


def _validate_message(message: str) -> str:
    clean = (message or "").strip()
    if not clean:
        raise DomainException("A notification requires a message", error_code="INVALID_NOTIFICATION_MESSAGE")
    return clean


@dataclass
class Notification:
    id: NotificationId
    tenant_id: TenantId
    recipient_id: AgentId
    kind: NotificationKind
    message: str
    lead_id: Optional[LeadId] = None
    intake_record_id: Optional[IntakeRecordId] = None
    is_read: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def create(
        cls,
        tenant_id: Union[str, UUID, TenantId],
        recipient_id: Union[str, UUID, AgentId],
        kind: Union[str, NotificationKind],
        message: str,
        lead_id: Optional[Union[str, UUID, LeadId]] = None,
        intake_record_id: Optional[Union[str, UUID, IntakeRecordId]] = None,
        notification_id: Optional[Union[str, UUID, NotificationId]] = None,
        is_read: bool = False,
        created_at: Optional[datetime] = None,
    ) -> "Notification":
        """Factory method that encapsulates Value Object construction and the
        notice's invariants."""
        tenant_id_vo = tenant_id if isinstance(tenant_id, TenantId) else TenantId(tenant_id)
        recipient_id_vo = recipient_id if isinstance(recipient_id, AgentId) else AgentId(recipient_id)
        kind_vo = kind if isinstance(kind, NotificationKind) else NotificationKind(kind)
        notification_id_vo = (
            notification_id if isinstance(notification_id, NotificationId) else NotificationId(notification_id)
        )
        lead_id_vo = lead_id if (lead_id is None or isinstance(lead_id, LeadId)) else LeadId(lead_id)
        intake_record_id_vo = (
            intake_record_id
            if (intake_record_id is None or isinstance(intake_record_id, IntakeRecordId))
            else IntakeRecordId(intake_record_id)
        )

        clean_message = _validate_message(message)

        return cls(
            id=notification_id_vo,
            tenant_id=tenant_id_vo,
            recipient_id=recipient_id_vo,
            kind=kind_vo,
            message=clean_message,
            lead_id=lead_id_vo,
            intake_record_id=intake_record_id_vo,
            is_read=is_read,
            created_at=created_at or datetime.now(timezone.utc),
        )

    def mark_as_read(self) -> None:
        # Idempotent on purpose: "mark all as read" walks every notice and
        # re-marking one already read is the normal case, not an error.
        self.is_read = True
