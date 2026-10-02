from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from domain.records.intake_record import IntakeRecord
from domain.value_objects.enums import IntakeRecordStatus


class IntakeRecordRepositoryPort(ABC):
    @abstractmethod
    def save(self, record: IntakeRecord) -> IntakeRecord: ...

    @abstractmethod
    def get_by_id_and_tenant(self, record_id: UUID, tenant_id: UUID) -> Optional[IntakeRecord]: ...

    @abstractmethod
    def claim_unpromoted(self, record_id: UUID, tenant_id: UUID) -> Optional[IntakeRecord]:
        """Take the record for the caller's transaction, or None if it is not open.

        Open means PENDING or REJECTED: a PROMOTED record already became a lead and a
        DISCARDED one was closed by a manager, so neither may be closed again.
        The guard against two concurrent runs closing the same record: a manual
        reprocess landing on a job a worker is still draining."""

    @abstractmethod
    def list_by_tenant(
        self,
        tenant_id: UUID,
        status: Optional[IntakeRecordStatus] = None,
        job_id: Optional[UUID] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[IntakeRecord]: ...

    @abstractmethod
    def count_by_tenant(
        self, tenant_id: UUID, status: Optional[IntakeRecordStatus] = None, job_id: Optional[UUID] = None,
    ) -> int: ...

    @abstractmethod
    def count_by_source(self, tenant_id: UUID, source_id: UUID) -> int: ...
