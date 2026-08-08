from abc import ABC, abstractmethod
from uuid import UUID

from application.dtos.commands import MarkNotificationReadCommand, NotificationsPageResult
from application.dtos.queries import GetNotificationsQuery


class GetNotificationsInputPort(ABC):
    @abstractmethod
    def execute(self, query: GetNotificationsQuery) -> NotificationsPageResult:
        pass


class MarkNotificationReadInputPort(ABC):
    @abstractmethod
    def execute(self, command: MarkNotificationReadCommand) -> None:
        pass


class MarkAllNotificationsReadInputPort(ABC):
    @abstractmethod
    def execute(self, recipient_id: UUID) -> int:
        pass
