from abc import ABC, abstractmethod
from uuid import UUID

class ProcessBatchInputPort(ABC):
    @abstractmethod
    def execute(self, tenant_id: UUID, job_id: UUID) -> None:
        pass
