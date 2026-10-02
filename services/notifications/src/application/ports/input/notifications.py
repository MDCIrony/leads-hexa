from abc import ABC, abstractmethod
from uuid import UUID

from application.dtos.notifications import (
    GetNotificationsQuery,
    MarkNotificationReadCommand,
    NotificationsPageResult,
)


class GetNotificationsInputPort(ABC):
    @abstractmethod
    def execute(self, query: GetNotificationsQuery) -> NotificationsPageResult: ...


class MarkNotificationReadInputPort(ABC):
    @abstractmethod
    def execute(self, command: MarkNotificationReadCommand) -> None: ...


class MarkAllNotificationsReadInputPort(ABC):
    @abstractmethod
    def execute(self, recipient_id: UUID) -> int: ...
