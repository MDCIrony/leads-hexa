import abc
from typing import List, Optional
from uuid import UUID

from domain.entities.intake_job import IntakeJob
from domain.value_objects.enums import IntakeJobStatus


class IntakeJobRepositoryPort(abc.ABC):
    @abc.abstractmethod
    def save(self, job: IntakeJob) -> IntakeJob: ...

    @abc.abstractmethod
    def get_by_id_and_tenant(self, job_id: UUID, tenant_id: UUID) -> Optional[IntakeJob]: ...

    @abc.abstractmethod
    def list_by_tenant(
        self,
        tenant_id: UUID,
        status: Optional[IntakeJobStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[IntakeJob]: ...

    @abc.abstractmethod
    def count_by_tenant(self, tenant_id: UUID, status: Optional[IntakeJobStatus] = None) -> int: ...
