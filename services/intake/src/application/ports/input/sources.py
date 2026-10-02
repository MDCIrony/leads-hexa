from abc import ABC, abstractmethod
from uuid import UUID

from application.dtos.sources import (
    CreateLeadSourceCommand,
    GetLeadSourcesQuery,
    LeadSourcesPageResult,
    UpdateLeadSourceCommand,
)
from domain.sources.lead_source import LeadSource


class CreateLeadSourceInputPort(ABC):
    @abstractmethod
    def execute(self, command: CreateLeadSourceCommand) -> LeadSource: ...


class GetLeadSourcesInputPort(ABC):
    @abstractmethod
    def execute(self, query: GetLeadSourcesQuery) -> LeadSourcesPageResult: ...


class UpdateLeadSourceInputPort(ABC):
    @abstractmethod
    def execute(self, command: UpdateLeadSourceCommand) -> LeadSource: ...


class DeleteLeadSourceInputPort(ABC):
    @abstractmethod
    def execute(self, tenant_id: UUID, source_id: UUID) -> None: ...
