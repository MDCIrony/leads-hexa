from abc import ABC, abstractmethod
from uuid import UUID

from application.dtos.commands import IngestLeadCommand, LeadProcessedResult
from domain.value_objects.enums import LeadSourceKind

class IngestLeadInputPort(ABC):
    @abstractmethod
    def resolve_source_id(self, tenant_id: UUID, kind: LeadSourceKind) -> UUID:
        pass

    @abstractmethod
    def execute(self, command: IngestLeadCommand) -> LeadProcessedResult:
        pass
