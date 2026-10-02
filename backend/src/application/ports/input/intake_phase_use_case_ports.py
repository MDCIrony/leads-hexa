from abc import ABC, abstractmethod
from uuid import UUID

from application.dtos.commands import ReceiveIntakeCommand, ReceiveIntakeResult


class ReceiveIntakeInputPort(ABC):
    @abstractmethod
    def execute(self, command: ReceiveIntakeCommand) -> ReceiveIntakeResult:
        pass


class ProcessIntakeJobInputPort(ABC):
    @abstractmethod
    def execute(self, tenant_id: UUID, job_id: UUID) -> bool:
        """True if a record raised and stayed PENDING, so the job needs another run."""
