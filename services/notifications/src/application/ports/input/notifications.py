from abc import ABC, abstractmethod
from uuid import UUID

from application.dtos.notifications import (
    GetNotificationsQuery,
    MarkNotificationReadCommand,
    NotificationsPageResult,
)
from application.ports.output.unit_of_work import UnitOfWorkPort


class GetNotificationsInputPort(ABC):
    @abstractmethod
    def execute(self, query: GetNotificationsQuery) -> NotificationsPageResult: ...


class MarkNotificationReadInputPort(ABC):
    @abstractmethod
    def execute(self, command: MarkNotificationReadCommand) -> None: ...


class MarkAllNotificationsReadInputPort(ABC):
    @abstractmethod
    def execute(self, recipient_id: UUID) -> int: ...


class NotificationHandlerInputPort(ABC):
    @abstractmethod
    def apply(self, event_type: str, tenant_id: str, payload: dict, uow: UnitOfWorkPort) -> None:
        """Turns an internal event into notices, inside the unit of work the consumer adapter owns."""
