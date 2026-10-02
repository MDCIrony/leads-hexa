from typing import List
from uuid import UUID

from application.ports.output.unit_of_work_port import UnitOfWorkPort
from domain.entities.notification import Notification
from domain.value_objects.enums import AgentRole, NotificationKind


class NotificationHandler:
    """Turns internal events into notices for whoever must act.

    Works inside the unit of work it is handed and never opens its own: the
    consumer marks the event processed in that same transaction, so a notice
    either lands together with the mark or not at all."""

    def apply(self, event_type: str, tenant_id: str, payload: dict, uow: UnitOfWorkPort) -> None:
        if event_type == "LeadAssigned":
            self._notify(uow, tenant_id, [payload["agent_id"]], NotificationKind.LEAD_ASSIGNED,
                         "Tienes un lead nuevo asignado", lead_id=payload["lead_id"])
        elif event_type == "LeadReassigned":
            self._notify(uow, tenant_id, [payload["agent_id"]], NotificationKind.LEAD_REASSIGNED,
                         "Te han reasignado un lead", lead_id=payload["lead_id"])
        elif event_type == "LeadLeftUnassigned":
            self._notify(uow, tenant_id, self._managers_of(uow, tenant_id),
                         NotificationKind.LEAD_LEFT_UNASSIGNED,
                         "Un lead no encontró asesor y espera asignación manual",
                         lead_id=payload["lead_id"])
        elif event_type == "IntakeRejected":
            self._notify(uow, tenant_id, self._managers_of(uow, tenant_id),
                         NotificationKind.INTAKE_REJECTED,
                         f"Un registro de entrada no se pudo interpretar: {payload['reason']}",
                         intake_record_id=payload["intake_record_id"])
        # Anything else on the topic is not ours to act on.

    @staticmethod
    def _managers_of(uow: UnitOfWorkPort, tenant_id: str) -> List[str]:
        # Filtered here rather than in a new repository method: an
        # organization has a handful of managers, and the port already
        # answers "everyone in this organization".
        agents = uow.agents.list_by_tenant(UUID(tenant_id), limit=10_000)
        return [
            str(agent.id.value)
            for agent in agents
            if agent.role == AgentRole.MANAGER and agent.is_active
        ]

    @staticmethod
    def _notify(uow, tenant_id, recipient_ids, kind, message, lead_id=None, intake_record_id=None) -> None:
        for recipient_id in recipient_ids:
            uow.notifications.save(Notification.create(
                tenant_id=tenant_id,
                recipient_id=recipient_id,
                kind=kind,
                message=message,
                lead_id=lead_id,
                intake_record_id=intake_record_id,
            ))
