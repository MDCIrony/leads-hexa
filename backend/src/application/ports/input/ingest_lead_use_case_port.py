from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from application.dtos.commands import IngestLeadCommand, LeadProcessedResult
from domain.entities.intake_record import IntakeRecord
from domain.value_objects.enums import LeadSourceKind

class IngestLeadInputPort(ABC):
    @abstractmethod
    def resolve_source_id(self, tenant_id: UUID, kind: LeadSourceKind) -> UUID:
        pass

    @abstractmethod
    def execute(
        self,
        command: IngestLeadCommand,
        existing_record: Optional[IntakeRecord] = None,
    ) -> LeadProcessedResult:
        pass
