from abc import ABC, abstractmethod
from uuid import UUID
from application.dtos.commands import BatchProcessResult

class ProcessBatchInputPort(ABC):
    @abstractmethod
    def execute(self, file_content: bytes, filename: str, tenant_id: UUID) -> BatchProcessResult:
        pass
