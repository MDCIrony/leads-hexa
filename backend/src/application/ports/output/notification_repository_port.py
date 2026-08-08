import abc
from typing import List, Optional
from uuid import UUID

from domain.entities.notification import Notification


class NotificationRepositoryPort(abc.ABC):
    @abc.abstractmethod
    def save(self, notification: Notification) -> Notification: ...

    # get_by_id_and_recipient, not get_by_id_and_tenant: isolation here is per
    # recipient, not per organization — two agents of the same tenant must not
    # be able to read each other's notices.
    @abc.abstractmethod
    def get_by_id_and_recipient(
        self, notification_id: UUID, recipient_id: UUID
    ) -> Optional[Notification]: ...

    @abc.abstractmethod
    def list_by_recipient(
        self,
        recipient_id: UUID,
        unread_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Notification]: ...

    @abc.abstractmethod
    def count_by_recipient(self, recipient_id: UUID, unread_only: bool = False) -> int: ...

    @abc.abstractmethod
    def mark_all_read(self, recipient_id: UUID) -> int: ...
