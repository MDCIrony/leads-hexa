from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID


class ClockPort(ABC):
    @abstractmethod
    def now(self) -> datetime:
        """The current instant, timezone-aware in UTC."""


class IdGeneratorPort(ABC):
    @abstractmethod
    def new_id(self) -> UUID: ...
