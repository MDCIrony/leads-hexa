from abc import ABC, abstractmethod
from uuid import UUID

from domain.notifications.notification import Notification


class NotificationRepositoryPort(ABC):
    @abstractmethod
    def save(self, notification: Notification) -> Notification: ...

    # get_by_id_and_recipient, not get_by_id_and_tenant: isolation here is per
    # recipient, not per organization — two agents of the same tenant must not
    # be able to read each other's notices.
    @abstractmethod
    def get_by_id_and_recipient(self, notification_id: UUID, recipient_id: UUID) -> Notification | None: ...

    @abstractmethod
    def list_by_recipient(
        self, recipient_id: UUID, unread_only: bool = False, limit: int = 100, offset: int = 0
    ) -> list[Notification]: ...

    @abstractmethod
    def count_by_recipient(self, recipient_id: UUID, unread_only: bool = False) -> int: ...

    @abstractmethod
    def mark_all_read(self, recipient_id: UUID) -> int: ...
