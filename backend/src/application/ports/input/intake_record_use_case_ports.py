from abc import ABC, abstractmethod
from uuid import UUID

from application.dtos.commands import (
    IntakeRecordsPageResult,
    LeadProcessedResult,
    PromoteIntakeRecordCommand,
)
from application.dtos.queries import GetIntakeRecordsQuery


class GetIntakeRecordsInputPort(ABC):
    @abstractmethod
    def execute(self, query: GetIntakeRecordsQuery) -> IntakeRecordsPageResult:
        pass


class PromoteIntakeRecordInputPort(ABC):
    @abstractmethod
    def execute(self, command: PromoteIntakeRecordCommand) -> LeadProcessedResult:
        pass


class DiscardIntakeRecordInputPort(ABC):
    @abstractmethod
    def execute(self, tenant_id: UUID, record_id: UUID) -> None:
        pass
