from typing import Callable, List
from uuid import UUID

from application.ports.output.unit_of_work_port import UnitOfWorkPort
from domain.entities.notification import Notification
from domain.events.notification_events import (
    IntakeRejected,
    LeadAssigned,
    LeadLeftUnassigned,
    LeadReassigned,
)
from domain.value_objects.enums import AgentRole, NotificationKind


class NotificationHandler:
    """Turns the events of a run into notices for whoever must act.

    Opens its own unit of work on purpose: the event arrives once the use
    case's transaction already committed, and that is the point — a notice
    that fails must not undo a lead that was saved."""

    def __init__(self, uow_factory: Callable[[], UnitOfWorkPort]) -> None:
        self.uow_factory = uow_factory

    def handle_lead_assigned(self, event: LeadAssigned) -> None:
        self._notify(
            tenant_id=event.tenant_id,
            recipient_ids=[event.agent_id],
            kind=NotificationKind.LEAD_ASSIGNED,
            message="Tienes un lead nuevo asignado",
            lead_id=event.lead_id,
        )

    def handle_lead_reassigned(self, event: LeadReassigned) -> None:
        self._notify(
            tenant_id=event.tenant_id,
            recipient_ids=[event.agent_id],
            kind=NotificationKind.LEAD_REASSIGNED,
            message="Te han reasignado un lead",
            lead_id=event.lead_id,
        )

    def handle_lead_left_unassigned(self, event: LeadLeftUnassigned) -> None:
        self._notify(
            tenant_id=event.tenant_id,
            recipient_ids=self._managers_of(event.tenant_id),
            kind=NotificationKind.LEAD_LEFT_UNASSIGNED,
            message="Un lead no encontró asesor y espera asignación manual",
            lead_id=event.lead_id,
        )

    def handle_intake_rejected(self, event: IntakeRejected) -> None:
        self._notify(
            tenant_id=event.tenant_id,
            recipient_ids=self._managers_of(event.tenant_id),
            kind=NotificationKind.INTAKE_REJECTED,
            message=f"Un registro de entrada no se pudo interpretar: {event.reason}",
            intake_record_id=event.intake_record_id,
        )

    def _managers_of(self, tenant_id: str) -> List[str]:
        with self.uow_factory() as uow:
            # Filtered here rather than in a new repository method: an
            # organization has a handful of managers, and the port already
            # answers "everyone in this organization".
            agents = uow.agents.list_by_tenant(UUID(tenant_id), limit=10_000)
        return [
            str(agent.id.value)
            for agent in agents
            if agent.role == AgentRole.MANAGER and agent.is_active
        ]

    def _notify(self, tenant_id, recipient_ids, kind, message, lead_id=None, intake_record_id=None) -> None:
        if not recipient_ids:
            return
        with self.uow_factory() as uow:
            for recipient_id in recipient_ids:
                uow.notifications.save(Notification.create(
                    tenant_id=tenant_id,
                    recipient_id=recipient_id,
                    kind=kind,
                    message=message,
                    lead_id=lead_id,
                    intake_record_id=intake_record_id,
                ))
