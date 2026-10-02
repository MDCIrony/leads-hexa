from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from application.ports.output.member_repository import MemberRepositoryPort
from application.ports.output.notification_repository import NotificationRepositoryPort
from application.ports.output.processed_event_repository import ProcessedEventRepositoryPort


class UnitOfWorkPort(ABC):
    notifications: NotificationRepositoryPort
    members: MemberRepositoryPort
    processed_events: ProcessedEventRepositoryPort

    def __enter__(self) -> UnitOfWorkPort:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()

    @abstractmethod
    def commit(self) -> None: ...

    @abstractmethod
    def rollback(self) -> None: ...
