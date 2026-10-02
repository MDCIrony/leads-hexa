from abc import ABC, abstractmethod
from uuid import UUID

from application.dtos.records import (
    GetIntakeRecordsQuery,
    IntakeRecordsPageResult,
    IntakeStatsResult,
    LeadProcessedResult,
    PromoteIntakeRecordCommand,
)


class GetIntakeRecordsInputPort(ABC):
    @abstractmethod
    def execute(self, query: GetIntakeRecordsQuery) -> IntakeRecordsPageResult: ...


class PromoteIntakeRecordInputPort(ABC):
    @abstractmethod
    def execute(self, command: PromoteIntakeRecordCommand) -> LeadProcessedResult: ...


class DiscardIntakeRecordInputPort(ABC):
    @abstractmethod
    def execute(self, tenant_id: UUID, record_id: UUID) -> None: ...


class GetIntakeStatsInputPort(ABC):
    @abstractmethod
    def execute(self, tenant_id: UUID) -> IntakeStatsResult: ...
