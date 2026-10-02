from uuid import UUID

from application.dtos.notifications import MarkNotificationReadCommand
from application.ports.input.notifications import (
    MarkAllNotificationsReadInputPort,
    MarkNotificationReadInputPort,
)
from application.ports.output.unit_of_work import UnitOfWorkPort
from domain.exceptions import DomainException


class MarkNotificationReadUseCase(MarkNotificationReadInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, command: MarkNotificationReadCommand) -> None:
        with self.uow:
            # A notice belonging to another recipient must read back as missing.
            notification = self.uow.notifications.get_by_id_and_recipient(
                command.notification_id, command.recipient_id
            )
            if notification is None:
                raise DomainException("La notificación no existe", error_code="NOTIFICATION_NOT_FOUND")
            notification.mark_as_read()
            self.uow.notifications.save(notification)


class MarkAllNotificationsReadUseCase(MarkAllNotificationsReadInputPort):
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self.uow = uow

    def execute(self, recipient_id: UUID) -> int:
        with self.uow:
            return self.uow.notifications.mark_all_read(recipient_id)
