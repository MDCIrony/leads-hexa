from abc import ABC, abstractmethod
from uuid import UUID

from application.dtos.commands import (
    CreateLeadSourceCommand,
    LeadSourcesPageResult,
    UpdateLeadSourceCommand,
)
from application.dtos.queries import GetLeadSourcesQuery
from domain.entities.lead_source import LeadSource


class CreateLeadSourceInputPort(ABC):
    @abstractmethod
    def execute(self, command: CreateLeadSourceCommand) -> LeadSource:
        pass


class GetLeadSourcesInputPort(ABC):
    @abstractmethod
    def execute(self, query: GetLeadSourcesQuery) -> LeadSourcesPageResult:
        pass


class UpdateLeadSourceInputPort(ABC):
    @abstractmethod
    def execute(self, command: UpdateLeadSourceCommand) -> LeadSource:
        pass


class DeleteLeadSourceInputPort(ABC):
    @abstractmethod
    def execute(self, tenant_id: UUID, source_id: UUID) -> None:
        pass
