from abc import ABC, abstractmethod
from uuid import UUID

from application.dtos.reception import IngestLeadCommand, ReceiveIntakeCommand, ReceiveIntakeResult
from application.dtos.records import LeadProcessedResult
from domain.records.intake_record import IntakeRecord


class ReceiveIntakeInputPort(ABC):
    @abstractmethod
    def execute(self, command: ReceiveIntakeCommand) -> ReceiveIntakeResult: ...


class ProcessBatchInputPort(ABC):
    @abstractmethod
    def execute(self, tenant_id: UUID, job_id: UUID) -> None: ...


class ProcessIntakeJobInputPort(ABC):
    @abstractmethod
    def execute(self, tenant_id: UUID, job_id: UUID) -> bool:
        """True if a record raised and stayed PENDING, so the job needs another run."""


class IngestLeadInputPort(ABC):
    @abstractmethod
    def execute(self, command: IngestLeadCommand, existing_record: IntakeRecord) -> LeadProcessedResult: ...
