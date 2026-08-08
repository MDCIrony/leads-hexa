import abc
from typing import List, Optional
from uuid import UUID

from domain.entities.intake_record import IntakeRecord
from domain.value_objects.enums import IntakeRecordStatus


class IntakeRecordRepositoryPort(abc.ABC):
    @abc.abstractmethod
    def save(self, record: IntakeRecord) -> IntakeRecord: ...

    @abc.abstractmethod
    def get_by_id_and_tenant(self, record_id: UUID, tenant_id: UUID) -> Optional[IntakeRecord]: ...

    @abc.abstractmethod
    def list_by_tenant(
        self,
        tenant_id: UUID,
        status: Optional[IntakeRecordStatus] = None,
        job_id: Optional[UUID] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[IntakeRecord]: ...

    @abc.abstractmethod
    def count_by_tenant(
        self,
        tenant_id: UUID,
        status: Optional[IntakeRecordStatus] = None,
        job_id: Optional[UUID] = None,
    ) -> int: ...
