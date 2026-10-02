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
    def claim_unpromoted(self, record_id: UUID, tenant_id: UUID) -> Optional[IntakeRecord]:
        """Take this record for the caller's transaction, or None unless it is
        PENDING or REJECTED (already a lead, or discarded).

        The one guard against processing the same record twice at once. Two
        concurrent runs over one job — a manual reprocess landing on a job the
        RabbitMQ worker is already draining — used to read the same PENDING
        rows and each create its own Lead from them: the same person, twice,
        under two identifiers, published twice on the outbound channel where no
        event_id can reconcile them."""

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
